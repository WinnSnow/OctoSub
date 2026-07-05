# -*- coding: utf-8 -*-
from poster_match_service import match_posters_for_messages
from structured_logging import log_event
from task_service import cancel_task, create_task, enqueue_heavy_task, get_task, is_cancel_requested, run_task_with_status
from telegram_service import get_active_proxy_config
from utils import safe_error_detail


POSTER_BACKFILL_CONCURRENCY = 5
_POSTER_BACKFILL_TASK = None
_POSTER_BACKFILL_TASK_ID: str | None = None
_PENDING_POSTER_BACKFILL_IDS: set[int] = set()


def _dedupe_message_ids(message_ids: list[int]) -> list[int]:
    seen = set()
    deduped = []
    for message_id in message_ids or []:
        try:
            value = int(message_id)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


async def backfill_posters_for_messages(message_ids: list[int], task_id: str | None = None) -> dict:
    deduped_ids = _dedupe_message_ids(message_ids)
    if not deduped_ids:
        log_event("scrape.poster_backfill.skipped_empty")
        return {
            "processed_messages": 0,
            "updated_messages": 0,
            "tmdb_requests": 0,
            "batches": 0,
            "queued_messages": 0,
        }

    log_event("scrape.poster_backfill.started", message_count=len(deduped_ids), task_id=task_id)
    stats = await match_posters_for_messages(
        deduped_ids,
        proxy_config=get_active_proxy_config(),
        concurrency=POSTER_BACKFILL_CONCURRENCY,
        task_id=task_id,
    )
    log_event(
        "scrape.poster_backfill.completed",
        task_id=task_id,
        updated_messages=stats.get("updated_messages"),
        processed_messages=stats.get("processed_messages"),
    )
    return stats


def _merge_stats(total_stats: dict, batch_stats: dict, *, batch_size: int) -> dict:
    total_stats["batches"] = int(total_stats.get("batches") or 0) + 1
    total_stats["queued_messages"] = int(total_stats.get("queued_messages") or 0) + batch_size
    for key in (
        "processed_messages",
        "unique_media_keys",
        "skipped_non_media",
        "database_key_cache_hits",
        "poster_cache_hits",
        "tmdb_requests",
        "updated_messages",
    ):
        total_stats[key] = int(total_stats.get(key) or 0) + int(batch_stats.get(key) or 0)
    if batch_stats.get("cancelled"):
        total_stats["cancelled"] = True
    total_stats["current"] = total_stats.get("processed_messages", 0)
    total_stats["total"] = total_stats.get("queued_messages", 0)
    return total_stats


async def run_poster_backfill_task(task_id: str) -> None:
    global _POSTER_BACKFILL_TASK, _POSTER_BACKFILL_TASK_ID
    try:
        await run_task_with_status(
            task_id,
            lambda: _run_poster_backfill_batches(task_id),
            success_message=lambda stats: f"自动补海报完成，已更新 {stats.get('updated_messages', 0)} 条消息",
            failure_message="自动补海报任务失败",
            exception_error=safe_error_detail("自动补海报任务失败"),
            log_event_name="scrape.poster_backfill.failed",
            log_fields=lambda exc: {"error_type": type(exc).__name__},
            log_exception=False,
        )
    finally:
        if _POSTER_BACKFILL_TASK_ID == task_id:
            _POSTER_BACKFILL_TASK = None
            _POSTER_BACKFILL_TASK_ID = None


async def _run_poster_backfill_batches(task_id: str) -> dict:
    total_stats = {
        "processed_messages": 0,
        "unique_media_keys": 0,
        "skipped_non_media": 0,
        "database_key_cache_hits": 0,
        "poster_cache_hits": 0,
        "tmdb_requests": 0,
        "updated_messages": 0,
        "batches": 0,
        "queued_messages": 0,
    }
    while _PENDING_POSTER_BACKFILL_IDS:
        if is_cancel_requested(task_id):
            total_stats["cancelled"] = True
            cancel_task(task_id, "自动补海报已停止", total_stats)
            return total_stats
        batch_ids = sorted(_PENDING_POSTER_BACKFILL_IDS)
        _PENDING_POSTER_BACKFILL_IDS.clear()
        batch_stats = await backfill_posters_for_messages(batch_ids, task_id=task_id)
        total_stats = _merge_stats(total_stats, batch_stats, batch_size=len(batch_ids))
        if batch_stats.get("cancelled"):
            return total_stats
    return total_stats


def schedule_poster_backfill(message_ids: list[int]) -> str | None:
    global _POSTER_BACKFILL_TASK, _POSTER_BACKFILL_TASK_ID
    deduped_ids = _dedupe_message_ids(message_ids)
    if not deduped_ids:
        return None
    _PENDING_POSTER_BACKFILL_IDS.update(deduped_ids)

    if _POSTER_BACKFILL_TASK and not _POSTER_BACKFILL_TASK.done() and _POSTER_BACKFILL_TASK_ID:
        log_event(
            "scrape.poster_backfill.appended",
            task_id=_POSTER_BACKFILL_TASK_ID,
            message_count=len(deduped_ids),
        )
        return _POSTER_BACKFILL_TASK_ID

    if _POSTER_BACKFILL_TASK_ID:
        try:
            task = get_task(_POSTER_BACKFILL_TASK_ID)
            if task.get("status") in {"queued", "running", "cancel_requested"}:
                log_event(
                    "scrape.poster_backfill.appended",
                    task_id=_POSTER_BACKFILL_TASK_ID,
                    message_count=len(deduped_ids),
                    status=task.get("status"),
                )
                return _POSTER_BACKFILL_TASK_ID
        except Exception:
            _POSTER_BACKFILL_TASK_ID = None

    task_id = create_task(
        "poster_match",
        "自动补海报",
        total=len(_PENDING_POSTER_BACKFILL_IDS),
        message="自动补海报任务排队中...",
        status="queued",
        result={"auto_backfill": True, "queued_messages": len(_PENDING_POSTER_BACKFILL_IDS), "batches": 0},
    )
    _POSTER_BACKFILL_TASK_ID = task_id
    _POSTER_BACKFILL_TASK = enqueue_heavy_task(task_id, lambda: run_poster_backfill_task(task_id))
    return task_id
