# -*- coding: utf-8 -*-
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from config import DB_PATH
from db import connect_db
from media_candidate_service import MediaCandidate, analyze_media_candidate
from message_cleaner_service import CleanMessageResult, INTERMEDIATE_SCORE_THRESHOLD, clean_message_text
from message_extraction_service import filter_message_text, is_promotional_message, parse_structured_format
from scrape_link_collector_service import dedupe_preserve_order, extract_link_candidates, has_resource_link_entrypoint
from structured_logging import log_event
from task_service import TASK_PROGRESS, update_task


SCRAPE_COMMIT_BATCH_SIZE = 1
SCRAPE_STOP_AFTER_EXISTING_STREAK = 10


@dataclass
class PendingScrapeMessage:
    message: Any
    title: str | None
    description: str | None
    clean_result: CleanMessageResult
    direct_links: list[str]
    intermediate_links: list[str]
    resolved_links: list[str] | None = None


async def _load_existing_message_ids(conn, channel_name: str, limit: int) -> set[int]:
    async with conn.execute(
        """
        SELECT message_id
        FROM messages
        WHERE channel_name = ?
        ORDER BY message_id DESC
        LIMIT ?
        """,
        (channel_name, limit),
    ) as cursor:
        return {row[0] for row in await cursor.fetchall()}


async def scrape_channel(
    channel_name: str,
    task_id: str | None = None,
    *,
    ensure_telegram_ready_fn: Callable[[], Awaitable[Any]],
    collect_resource_links_fn: Callable[[Any], Awaitable[list[str]]],
    extract_link_candidates_fn: Callable[..., dict] = extract_link_candidates,
    resolve_intermediate_links_fn: Callable[[list[str]], Awaitable[list[str]]] | None = None,
    db_path: str = DB_PATH,
    task_progress: dict = TASK_PROGRESS,
    update_task_fn: Callable[..., None] = update_task,
    parse_structured_format_fn: Callable[[Any], dict | None] = parse_structured_format,
    filter_message_text_fn: Callable[[str], str] = filter_message_text,
    is_promotional_message_fn: Callable[[str | None, str], bool] = is_promotional_message,
    dedupe_preserve_order_fn: Callable[[list[str]], list[str]] = dedupe_preserve_order,
    has_resource_link_entrypoint_fn: Callable[[Any], bool] = has_resource_link_entrypoint,
    analyze_media_candidate_fn: Callable[..., MediaCandidate] = analyze_media_candidate,
    should_cancel_fn: Callable[[str | None], bool] = lambda _task_id: False,
    commit_batch_size: int = SCRAPE_COMMIT_BATCH_SIZE,
    stop_after_existing_streak: int = SCRAPE_STOP_AFTER_EXISTING_STREAK,
    existing_prefetch_limit: int = 500,
) -> list[int]:
    client = await ensure_telegram_ready_fn()
    new_message_ids = []
    stats = {
        "raw_messages_seen": 0,
        "messages_inserted": 0,
        "skipped_existing": 0,
        "skipped_promotional": 0,
        "skipped_non_media": 0,
        "skipped_no_resource": 0,
        "skipped_weak_intermediate": 0,
        "intermediate_candidates": 0,
        "intermediate_resolved_messages": 0,
        "intermediate_requests": 0,
        "intermediate_successes": 0,
        "intermediate_failures": 0,
        "intermediate_timeouts": 0,
        "skip_reasons": {},
        "cancelled": False,
    }

    def record_skip(reason: str) -> None:
        stats["skip_reasons"][reason] = stats["skip_reasons"].get(reason, 0) + 1

    def publish_stats(extra: dict | None = None) -> None:
        if not task_id or task_id not in task_progress:
            return
        payload = {"scrape_stats": dict(stats)}
        if extra:
            payload.update(extra)
        update_task_fn(task_id, result_patch=payload)

    async with connect_db(db_path, timeout=60.0) as conn:
        try:
            entity = await client.get_entity(channel_name)
        except Exception as exc:
            log_event("scrape.channel.entity_failed", "warning", channel_name=channel_name, error_type=type(exc).__name__)
            return []

        log_event("scrape.channel.started", channel_name=channel_name)

        if task_id and task_id in task_progress:
            task_progress[task_id]["message"] = f"正在从 {entity.title} 获取消息..."

        msg_processed = 0
        pending_new_messages = 0
        pending_messages: list[PendingScrapeMessage] = []
        existing_streak = 0
        existing_message_ids = await _load_existing_message_ids(conn, channel_name, existing_prefetch_limit)
        async for message in client.iter_messages(entity, limit=200):
            if should_cancel_fn(task_id):
                stats["cancelled"] = True
                publish_stats()
                log_event("scrape.channel.cancelled", channel_name=channel_name, task_id=task_id)
                break
            if not message.text:
                continue
            stats["raw_messages_seen"] += 1

            if message.id in existing_message_ids:
                stats["skipped_existing"] += 1
                record_skip("existing_message")
                existing_streak += 1
                if pending_new_messages:
                    await conn.commit()
                    pending_new_messages = 0
                if existing_streak >= stop_after_existing_streak:
                    log_event(
                        "scrape.channel.existing_streak_stop",
                        channel_name=channel_name,
                        existing_streak=existing_streak,
                    )
                    break
                log_event("scrape.channel.existing_message", channel_name=channel_name, message_id=message.id)
                continue

            existing_streak = 0

            msg_processed += 1
            if task_id and task_id in task_progress:
                update_task_fn(
                    task_id,
                    message=f"正在解析 {entity.title}: 已处理 {msg_processed} 条，当前消息 {message.id}",
                    result_patch={"current_channel": channel_name, "current_channel_processed": msg_processed},
                )

            log_event("scrape.channel.message_processing", channel_name=channel_name, message_id=message.id)

            title, description, resource_url = None, None, None

            parsed_data = parse_structured_format_fn(message)
            if parsed_data:
                title = parsed_data["title"]
                description = parsed_data["description"]
            else:
                title = message.text.split("\n")[0].strip()
                description = filter_message_text_fn(message.text)

            clean_result = clean_message_text(title=title, raw_text=message.text)
            if not parsed_data:
                description = filter_message_text_fn(clean_result.content_text)

            link_candidates = extract_link_candidates_fn(message, text=clean_result.content_text)
            direct_links = list(link_candidates.get("direct_resource_links") or [])
            intermediate_links = list(link_candidates.get("intermediate_links") or [])

            if clean_result.hard_ad and not direct_links:
                stats["skipped_promotional"] += 1
                record_skip("promotional_message")
                publish_stats()
                log_event(
                    "scrape.channel.message_skipped",
                    channel_name=channel_name,
                    message_id=message.id,
                    reason="promotional_message",
                )
                continue

            should_resolve_intermediate = bool(
                clean_result.should_resolve_intermediate
                or (
                    intermediate_links
                    and not clean_result.hard_ad
                    and clean_result.intermediate_score >= INTERMEDIATE_SCORE_THRESHOLD
                )
            )

            if not direct_links and intermediate_links:
                stats["intermediate_candidates"] += 1
                stats["intermediate_requests"] += len(intermediate_links)
                if not should_resolve_intermediate:
                    stats["skipped_weak_intermediate"] += 1
                    record_skip("weak_intermediate_candidate")
                    publish_stats()
                    log_event(
                        "scrape.channel.message_skipped",
                        channel_name=channel_name,
                        message_id=message.id,
                        reason="weak_intermediate_candidate",
                        intermediate_score=clean_result.intermediate_score,
                    )
                    continue
            elif not direct_links and not intermediate_links:
                candidate = analyze_media_candidate_fn(title=title, raw_text=clean_result.content_text, links=[])
                if not candidate.is_media_candidate:
                    stats["skipped_non_media"] += 1
                    record_skip(candidate.skip_reason or "not_media_candidate")
                    publish_stats()
                    log_event(
                        "scrape.channel.message_skipped",
                        channel_name=channel_name,
                        message_id=message.id,
                        reason=candidate.skip_reason or "not_media_candidate",
                    )
                    continue
                stats["skipped_no_resource"] += 1
                record_skip("no_resource_link")
                publish_stats()
                log_event(
                    "scrape.channel.message_skipped",
                    channel_name=channel_name,
                    message_id=message.id,
                    reason="no_resource_link",
                )
                continue

            pending_messages.append(
                PendingScrapeMessage(
                    message=message,
                    title=title,
                    description=description,
                    clean_result=clean_result,
                    direct_links=direct_links,
                    intermediate_links=intermediate_links,
                    resolved_links=direct_links if direct_links else None,
                )
            )

        async def resolve_pending_message(pending: PendingScrapeMessage) -> None:
            if pending.resolved_links is not None:
                return
            if resolve_intermediate_links_fn:
                try:
                    pending.resolved_links = await resolve_intermediate_links_fn(pending.intermediate_links, stats=stats)
                except TypeError:
                    pending.resolved_links = await resolve_intermediate_links_fn(pending.intermediate_links)
            else:
                pending.resolved_links = await collect_resource_links_fn(pending.message)

        intermediate_pending = [item for item in pending_messages if item.resolved_links is None]
        if intermediate_pending:
            settled = await asyncio.gather(
                *(resolve_pending_message(item) for item in intermediate_pending),
                return_exceptions=True,
            )
            for item, result in zip(intermediate_pending, settled, strict=True):
                if isinstance(result, Exception):
                    log_event(
                        "scrape.channel.intermediate_resolve_failed",
                        "warning",
                        channel_name=channel_name,
                        message_id=item.message.id,
                        error_type=type(result).__name__,
                    )
                    item.resolved_links = []
                elif item.resolved_links:
                    stats["intermediate_resolved_messages"] += 1
            publish_stats()

        for pending in pending_messages:
            message = pending.message
            all_found_links = pending.resolved_links or []
            resource_url = all_found_links[0] if all_found_links else None

            candidate = analyze_media_candidate_fn(
                title=pending.title,
                raw_text=pending.clean_result.content_text,
                links=all_found_links,
            )
            if not candidate.is_media_candidate:
                stats["skipped_non_media"] += 1
                record_skip(candidate.skip_reason or "not_media_candidate")
                publish_stats()
                log_event(
                    "scrape.channel.message_skipped",
                    channel_name=channel_name,
                    message_id=message.id,
                    reason=candidate.skip_reason or "not_media_candidate",
                    stage="post_resolution",
                )
                continue

            unique_links = dedupe_preserve_order_fn(candidate.resource_links or all_found_links)
            resource_url = candidate.primary_resource_url or resource_url
            if not resource_url:
                stats["skipped_no_resource"] += 1
                record_skip("no_resource_link")
                publish_stats()
                log_event(
                    "scrape.channel.message_skipped",
                    channel_name=channel_name,
                    message_id=message.id,
                    reason="no_resource_link",
                    stage="post_resolution",
                )
                continue

            title = candidate.clean_title or pending.title
            image_web_path = message.web_preview.url if message.web_preview else None
            if not title:
                continue

            await conn.execute(
                "INSERT INTO messages (channel_name, message_id, title, description, raw_text, publish_date, resource_url, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    channel_name,
                    message.id,
                    title,
                    pending.description,
                    message.text,
                    message.date,
                    resource_url,
                    image_web_path,
                ),
            )
            async with conn.execute("SELECT last_insert_rowid()") as cursor:
                db_message_id = (await cursor.fetchone())[0]
            new_message_ids.append(db_message_id)
            existing_message_ids.add(message.id)
            stats["messages_inserted"] += 1

            if unique_links:
                await conn.executemany(
                    "INSERT OR IGNORE INTO links (message_id, url) VALUES (?, ?)",
                    ((db_message_id, link) for link in unique_links),
                )
            pending_new_messages += 1
            publish_stats({"current_channel": channel_name, "current_channel_inserted": stats["messages_inserted"]})
            if pending_new_messages >= commit_batch_size:
                await conn.commit()
                pending_new_messages = 0

        if pending_new_messages:
            await conn.commit()

    log_event("scrape.channel.completed", channel_name=channel_name, inserted=len(new_message_ids), stats=stats)
    return new_message_ids
