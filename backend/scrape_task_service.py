# -*- coding: utf-8 -*-
import asyncio
from collections.abc import Awaitable, Callable

import aiosqlite

from config import DB_PATH
from scrape_telegram_readiness_service import TelegramScrapeUnavailable
from task_service import cancel_task, complete_task, create_task, fail_task, get_task, is_cancel_requested, run_task_with_status, update_task
from utils import safe_error_detail


async def get_channels_to_scrape(channel_name: str | None, db_path: str = DB_PATH) -> list[str]:
    if channel_name:
        return [channel_name]

    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("SELECT url FROM channels") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def run_scrape_task(
    channels: list[str],
    task_id: str,
    *,
    scrape_channel_fn: Callable[[str, str], Awaitable[list[int]]],
    schedule_poster_backfill_fn: Callable[[list[int]], str | None],
    update_task_fn: Callable[..., None] = update_task,
    complete_task_fn: Callable[..., None] = complete_task,
    fail_task_fn: Callable[..., None] = fail_task,
    cancel_task_fn: Callable[..., None] = cancel_task,
    is_cancel_requested_fn: Callable[[str | None], bool] = is_cancel_requested,
    get_task_fn: Callable[[str], dict] = get_task,
    safe_error_detail_fn: Callable[[str], str] = safe_error_detail,
) -> None:
    try:
        await run_task_with_status(
            task_id,
            lambda: _run_scrape_batches(
                channels,
                task_id,
                scrape_channel_fn=scrape_channel_fn,
                schedule_poster_backfill_fn=schedule_poster_backfill_fn,
                update_task_fn=update_task_fn,
                cancel_task_fn=cancel_task_fn,
                is_cancel_requested_fn=is_cancel_requested_fn,
                get_task_fn=get_task_fn,
            ),
            success_message=lambda result: "所有频道同步完成，已启动后台补海报" if result.get("poster_backfill_started") else "所有频道同步完成",
            failure_message=safe_error_detail_fn("同步出错"),
            exception_error=safe_error_detail_fn("同步出错"),
            log_event_name="scrape.task.failed",
            log_fields=lambda exc: {"error_type": type(exc).__name__},
            log_exception=False,
            complete_task_fn=complete_task_fn,
            fail_task_fn=fail_task_fn,
        )
    except TelegramScrapeUnavailable as exc:
        fail_task_fn(task_id, str(exc), str(exc))


async def _run_scrape_batches(
    channels: list[str],
    task_id: str,
    *,
    scrape_channel_fn: Callable[[str, str], Awaitable[list[int]]],
    schedule_poster_backfill_fn: Callable[[list[int]], str | None],
    update_task_fn: Callable[..., None],
    cancel_task_fn: Callable[..., None],
    is_cancel_requested_fn: Callable[[str | None], bool],
    get_task_fn: Callable[[str], dict],
) -> dict:
    def current_task_result() -> dict:
        try:
            result = get_task_fn(task_id).get("result", {})
            return dict(result) if isinstance(result, dict) else {}
        except Exception:
            return {}

    new_message_ids = []
    for index, channel in enumerate(channels, start=1):
        if is_cancel_requested_fn(task_id):
            result = {
                **current_task_result(),
                "channels_processed": index - 1,
                "messages_added": len(new_message_ids),
                "poster_backfill_started": False,
                "cancelled": True,
            }
            cancel_task_fn(task_id, "频道抓取已停止", result)
            return result
        update_task_fn(task_id, current=index - 1, message=f"正在抓取频道 {channel}")
        new_message_ids.extend(await scrape_channel_fn(channel, task_id))
        if is_cancel_requested_fn(task_id):
            result = {
                **current_task_result(),
                "channels_processed": index - 1,
                "messages_added": len(new_message_ids),
                "poster_backfill_started": False,
                "cancelled": True,
            }
            cancel_task_fn(task_id, "频道抓取已停止", result)
            return result
        update_task_fn(task_id, current=index, result_patch={"channels_processed": index})
    poster_backfill_task_id = schedule_poster_backfill_fn(new_message_ids)
    return {
        **current_task_result(),
        "channels_processed": len(channels),
        "messages_added": len(new_message_ids),
        "poster_backfill_started": bool(poster_backfill_task_id),
        "poster_backfill_task_id": poster_backfill_task_id,
    }


async def trigger_scrape_payload(
    channel_name: str | None,
    *,
    ensure_telegram_ready_fn: Callable[[], Awaitable[object]],
    scrape_channel_fn: Callable[[str, str], Awaitable[list[int]]],
    schedule_poster_backfill_fn: Callable[[list[int]], None],
    db_path: str = DB_PATH,
    create_task_fn: Callable[..., str] = create_task,
    create_background_task_fn: Callable[[Awaitable[None]], asyncio.Task] | None = asyncio.create_task,
    enqueue_task_fn: Callable[[str, Callable[[], Awaitable[None]]], None] | None = None,
) -> dict:
    await ensure_telegram_ready_fn()
    channels_to_scrape = await get_channels_to_scrape(channel_name, db_path)

    if not channels_to_scrape:
        return {"message": "没有配置任何频道。"}

    task_id = create_task_fn(
        "fetch",
        "频道抓取",
        total=len(channels_to_scrape),
        message="频道抓取任务排队中...",
        status="queued",
        channel="ALL" if not channel_name else channel_name,
    )

    async def run_task():
        await run_scrape_task(
            channels_to_scrape,
            task_id,
            scrape_channel_fn=scrape_channel_fn,
            schedule_poster_backfill_fn=schedule_poster_backfill_fn,
        )

    queued = bool(enqueue_task_fn)
    if enqueue_task_fn:
        enqueue_task_fn(task_id, run_task)
    elif create_background_task_fn:
        create_background_task_fn(run_task())
    if queued:
        return {"message": "抓取任务已加入后台队列", "task_id": task_id, "status": "queued"}
    return {"message": "抓取任务已启动", "task_id": task_id}
