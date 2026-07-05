# -*- coding: utf-8 -*-
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from media_candidate_service import analyze_media_candidate
from poster_fetch_service import PosterMatchResult
from poster_identity_service import build_media_identity
from poster_match_batch_db_service import (
    build_local_poster_reuse_keys,
    load_existing_tmdb_posters_by_key,
    read_target_messages,
)
from poster_match_cache_service import (
    apply_database_poster_hits,
    apply_poster_cache_hits,
    build_poster_cache_payload,
    poster_cache_ttl,
)
from poster_match_write_service import update_message_posters
from structured_logging import log_event

CacheGetFn = Callable[[str, str], Awaitable[dict | None]]
CacheSetFn = Callable[[str, str, dict, int], Awaitable[None]]
PosterFetchFn = Callable[[Any, dict | None], Awaitable[PosterMatchResult]]
UpdateTaskFn = Callable[..., None]
IsCancelRequestedFn = Callable[[str | None], bool]
CancelTaskFn = Callable[..., None]


def group_messages_by_media_key(messages: list[tuple]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for msg_id, title, raw_text, _image_url, tmdb_id, tmdb_type, year in messages:
        candidate = analyze_media_candidate(title=title, raw_text=raw_text)
        identity_title = candidate.clean_title or title
        identity_year = year or candidate.year
        identity_type = tmdb_type or candidate.media_type
        identity = build_media_identity(identity_title, raw_text, tmdb_id, identity_type, identity_year)
        if not identity.clean_title and not identity.tmdb_id:
            continue
        local_reuse_keys = build_local_poster_reuse_keys(
            identity_title,
            raw_text,
            tmdb_id,
            identity_type,
            identity_year,
        )
        group = groups.setdefault(
            identity.key,
            {
                "identity": identity,
                "message_ids": [],
                "allow_tmdb_lookup": False,
                "local_reuse_keys": [],
            },
        )
        group["message_ids"].append(msg_id)
        group["allow_tmdb_lookup"] = group["allow_tmdb_lookup"] or bool(tmdb_id) or candidate.allow_tmdb_lookup
        for key in local_reuse_keys:
            if key not in group["local_reuse_keys"]:
                group["local_reuse_keys"].append(key)
    return groups


def count_tmdb_skipped_messages(messages: list[tuple]) -> int:
    skipped = 0
    for _msg_id, title, raw_text, _image_url, tmdb_id, _tmdb_type, _year in messages:
        if tmdb_id:
            continue
        candidate = analyze_media_candidate(title=title, raw_text=raw_text)
        if not candidate.allow_tmdb_lookup:
            skipped += 1
    return skipped


async def match_posters_for_message_batch(
    *,
    db_path: str,
    message_ids: list[int] | None,
    proxy_config: dict | None,
    concurrency: int,
    ignore_cached_misses: bool,
    get_json_cache_fn: CacheGetFn,
    set_json_cache_fn: CacheSetFn,
    fetch_poster_for_identity_fn: PosterFetchFn,
    task_id: str | None = None,
    update_task_fn: UpdateTaskFn | None = None,
    is_cancel_requested_fn: IsCancelRequestedFn | None = None,
    cancel_task_fn: CancelTaskFn | None = None,
) -> dict:
    messages = await read_target_messages(db_path, message_ids)
    if not messages:
        return {
            "processed_messages": 0,
            "unique_media_keys": 0,
            "skipped_non_media": 0,
            "database_key_cache_hits": 0,
            "poster_cache_hits": 0,
            "tmdb_requests": 0,
            "updated_messages": 0,
        }

    groups = group_messages_by_media_key(messages)
    skipped_non_media = count_tmdb_skipped_messages(messages)
    excluded_ids = {row[0] for row in messages}
    existing_posters = await load_existing_tmdb_posters_by_key(db_path, excluded_ids)
    resolved: dict[str, PosterMatchResult] = {}
    stats = {
        "processed_messages": len(messages),
        "unique_media_keys": len(groups),
        "skipped_non_media": skipped_non_media,
        "database_key_cache_hits": 0,
        "poster_cache_hits": 0,
        "tmdb_requests": 0,
        "updated_messages": 0,
    }
    total = len(groups)
    current = 0
    completed_keys: set[str] = set()

    def is_cancel_requested() -> bool:
        return bool(task_id and is_cancel_requested_fn and is_cancel_requested_fn(task_id))

    def patch_task(message: str | None = None) -> None:
        if not task_id or not update_task_fn:
            return
        update_task_fn(
            task_id,
            current=current,
            total=total,
            message=message,
            result_patch={**stats, "current": current, "total": total},
        )

    def advance_key(key: str, message: str | None = None) -> None:
        nonlocal current
        if key in completed_keys:
            patch_task(message)
            return
        completed_keys.add(key)
        current += 1
        patch_task(message)

    def progress_message() -> str:
        return f"海报匹配进度 {min(current + 1, total)}/{total}" if total else "海报匹配进度完成"

    patch_task("正在准备海报匹配...")

    apply_database_poster_hits(groups, existing_posters, resolved, stats)
    await apply_poster_cache_hits(
        groups,
        resolved,
        stats,
        ignore_cached_misses=ignore_cached_misses,
        get_json_cache_fn=get_json_cache_fn,
    )

    semaphore = asyncio.Semaphore(max(1, concurrency))
    request_lock = asyncio.Lock()
    write_lock = asyncio.Lock()

    async def update_messages_for_key(key: str, result: PosterMatchResult | None):
        if not result or not result.poster_url:
            return
        async with write_lock:
            stats["updated_messages"] += await update_message_posters(
                db_path,
                groups[key]["message_ids"],
                result.poster_url,
            )

    for key, result in list(resolved.items()):
        await update_messages_for_key(key, result)
        advance_key(key, progress_message())

    for key, group in groups.items():
        if key not in resolved and not group.get("allow_tmdb_lookup"):
            advance_key(key, progress_message())

    tmdb_keys = [
        key
        for key, group in groups.items()
        if key not in completed_keys and key not in resolved and group.get("allow_tmdb_lookup")
    ]
    next_index = 0
    queue_lock = asyncio.Lock()

    async def claim_next_key() -> str | None:
        nonlocal next_index
        if is_cancel_requested():
            return None
        async with queue_lock:
            if is_cancel_requested() or next_index >= len(tmdb_keys):
                return None
            key = tmdb_keys[next_index]
            next_index += 1
            return key

    async def resolve_claimed_key(key: str):
        identity = groups[key]["identity"]
        async with semaphore:
            async with request_lock:
                stats["tmdb_requests"] += 1
            result = await fetch_poster_for_identity_fn(identity, proxy_config)
            resolved[key] = result
            await set_json_cache_fn(
                "poster_cache",
                f"poster:{key}",
                build_poster_cache_payload(key, result),
                poster_cache_ttl(result),
            )
            await update_messages_for_key(key, result)
            advance_key(key, progress_message())

    async def worker():
        while True:
            key = await claim_next_key()
            if key is None:
                return
            await resolve_claimed_key(key)

    worker_count = min(max(1, concurrency), len(tmdb_keys)) if tmdb_keys else 0
    if worker_count:
        await asyncio.gather(*(worker() for _ in range(worker_count)))

    cancelled = is_cancel_requested()
    if cancelled:
        stats.update({"cancelled": True, "current": current, "total": total})
        if task_id and cancel_task_fn:
            cancel_task_fn(
                task_id,
                f"海报匹配已停止，已更新 {stats.get('updated_messages', 0)} 条消息",
                stats,
            )
    else:
        stats.update({"current": current, "total": total})
        patch_task("海报匹配进度完成")

    log_event(
        "poster.match_batch.completed",
        processed_messages=stats["processed_messages"],
        unique_media_keys=stats["unique_media_keys"],
        database_key_cache_hits=stats["database_key_cache_hits"],
        poster_cache_hits=stats["poster_cache_hits"],
        tmdb_requests=stats["tmdb_requests"],
        updated_messages=stats["updated_messages"],
        cancelled=cancelled,
    )
    return stats
