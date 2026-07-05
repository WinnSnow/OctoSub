# -*- coding: utf-8 -*-
import asyncio
import random
from collections.abc import Awaitable, Callable

import aiosqlite

from config import DB_PATH
from message_extraction_service import filter_message_text, parse_structured_format
from poster_service import fetch_movie_poster
from scrape_link_collector_service import dedupe_preserve_order
from scrape_telegram_readiness_service import TelegramScrapeUnavailable
from structured_logging import log_event
from task_service import complete_task, create_task, fail_task, update_task
from utils import safe_error_detail


async def retry_single_message(
    channel_name: str,
    message_id: int,
    *,
    ensure_telegram_ready_fn: Callable[[], Awaitable[object]],
    collect_resource_links_fn: Callable[[object], Awaitable[list[str]]],
    fetch_movie_poster_fn: Callable[[str], Awaitable[str | None]] = fetch_movie_poster,
    db_path: str = DB_PATH,
) -> bool:
    try:
        client = await ensure_telegram_ready_fn()
    except TelegramScrapeUnavailable as exc:
        log_event("scrape.retry.telegram_unavailable", "warning", error_type=type(exc).__name__)
        return False

    try:
        try:
            entity = await client.get_entity(channel_name)
        except Exception:
            if "t.me/" in channel_name:
                channel_name = channel_name.split("t.me/")[-1].split("/")[0]
                entity = await client.get_entity(channel_name)
            else:
                raise

        message = await client.get_messages(entity, ids=message_id)
        if not message or not message.text:
            log_event("scrape.retry.message_missing", message_id=message_id)
            return False

        parsed_data = parse_structured_format(message)
        if parsed_data:
            title = parsed_data["title"]
            description = parsed_data["description"]
        else:
            title = message.text.split("\n")[0].strip()
            description = filter_message_text(message.text)

        all_found_links = await collect_resource_links_fn(message)
        resource_url = all_found_links[0] if all_found_links else None

        poster_url = await fetch_movie_poster_fn(title) if title else None
        image_web_path = poster_url if poster_url else (message.web_preview.url if message.web_preview else None)

        async with aiosqlite.connect(db_path) as conn:
            async with conn.execute(
                "SELECT id FROM messages WHERE channel_name = ? AND message_id = ?",
                (channel_name, message_id),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                db_id = row[0]

            await conn.execute(
                """
                UPDATE messages
                SET title = ?, description = ?, raw_text = ?, resource_url = ?, image_url = ?
                WHERE id = ?
                """,
                (title, description, message.text, resource_url, image_web_path, db_id),
            )

            await conn.execute("DELETE FROM links WHERE message_id = ?", (db_id,))
            unique_links = dedupe_preserve_order(all_found_links)
            if unique_links:
                await conn.executemany(
                    "INSERT OR IGNORE INTO links (message_id, url) VALUES (?, ?)",
                    ((db_id, link) for link in unique_links),
                )
            await conn.commit()
            return True
    except Exception as exc:
        log_event("scrape.retry.message_failed", "warning", message_id=message_id, error_type=type(exc).__name__)
        return False


async def get_missing_link_rows(channel_name: str, db_path: str = DB_PATH) -> list[tuple[int, str]]:
    async with aiosqlite.connect(db_path) as conn:
        query = "SELECT message_id, channel_name FROM messages WHERE (resource_url IS NULL OR resource_url = '')"
        params = []
        if channel_name != "all":
            query += " AND channel_name = ?"
            params.append(channel_name)
        async with conn.execute(query, tuple(params)) as cursor:
            return await cursor.fetchall()


async def run_retry_missing_links_batch(
    messages: list[tuple[int, str]],
    task_id: str,
    *,
    retry_single_message_fn: Callable[[str, int], Awaitable[bool]],
    update_task_fn: Callable[..., None] = update_task,
    complete_task_fn: Callable[..., None] = complete_task,
    fail_task_fn: Callable[..., None] = fail_task,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    random_uniform_fn: Callable[[float, float], float] = random.uniform,
) -> None:
    log_event("scrape.retry.batch_started", task_id=task_id, total=len(messages))
    success_count = 0
    try:
        for index, (message_id, channel_name) in enumerate(messages):
            update_task_fn(
                task_id,
                current=index + 1,
                message=f"正在处理 {index + 1}/{len(messages)} (ID: {message_id})",
            )
            await sleep_fn(random_uniform_fn(1.5, 3.0))
            if await retry_single_message_fn(channel_name, message_id):
                success_count += 1

        complete_task_fn(
            task_id,
            f"任务完成。成功更新: {success_count}/{len(messages)}",
            {"success_count": success_count, "total": len(messages)},
        )
        log_event("scrape.retry.batch_completed", task_id=task_id, success_count=success_count, total=len(messages))
    except Exception as exc:
        fail_task_fn(task_id, safe_error_detail("任务异常终止"), str(exc))
        log_event("scrape.retry.batch_failed", "warning", task_id=task_id, error_type=type(exc).__name__)


async def retry_missing_links_payload(
    channel_name: str,
    *,
    retry_single_message_fn: Callable[[str, int], Awaitable[bool]],
    db_path: str = DB_PATH,
    create_task_fn: Callable[..., str] = create_task,
    create_background_task_fn: Callable[[Awaitable[None]], asyncio.Task] = asyncio.create_task,
) -> dict:
    rows = await get_missing_link_rows(channel_name, db_path)

    if not rows:
        return {"status": "success", "message": "没有需要重试的消息", "count": 0, "task_id": None}

    task_id = create_task_fn(
        "retry",
        "补链重试",
        total=len(rows),
        message="正在初始化任务...",
        channel=channel_name,
    )

    create_background_task_fn(
        run_retry_missing_links_batch(
            rows,
            task_id,
            retry_single_message_fn=retry_single_message_fn,
        )
    )
    return {
        "status": "success",
        "message": f"已开始后台重试 {len(rows)} 条消息",
        "count": len(rows),
        "task_id": task_id,
    }
