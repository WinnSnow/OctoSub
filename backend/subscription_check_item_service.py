# -*- coding: utf-8 -*-
import inspect
from collections.abc import Awaitable, Callable

import aiosqlite

from config import DB_PATH, SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE
from subscription_check_repository import mark_subscription_checked
from subscription_check_search_service import search_subscription_results
from subscription_lifecycle_service import (
    evaluate_subscription_completion,
    get_missing_subscription_episodes,
    normalize_target_seasons,
)
from subscription_repository import get_subscription_active_state
from structured_logging import log_event
from subscription_transfer_decision_service import process_subscription_result

StopCheck = Callable[[], bool | Awaitable[bool]]


async def _should_stop(should_stop_fn: StopCheck | None) -> bool:
    if not should_stop_fn:
        return False
    result = should_stop_fn()
    if inspect.isawaitable(result):
        return bool(await result)
    return bool(result)


async def is_subscription_still_active(subscription_id: int, db_path: str = DB_PATH) -> bool:
    try:
        active = await get_subscription_active_state(subscription_id, db_path=db_path)
    except aiosqlite.Error:
        return True
    return bool(active) if active is not None else False


def build_subscription_dict(
    sub_id: int,
    keyword: str,
    media_type: str,
    sub_tmdb_id: int | None,
    sub_tmdb_type: str | None,
    sub_year: int | None,
    target_seasons=None,
) -> dict:
    return {
        "id": sub_id,
        "keyword": keyword,
        "media_type": media_type,
        "tmdb_id": sub_tmdb_id,
        "tmdb_type": sub_tmdb_type,
        "year": sub_year,
        "target_seasons": sorted(normalize_target_seasons(target_seasons) or []),
    }


async def process_subscription_check_item(
    subscription_row: tuple,
    jellyfin,
    proxy_config: dict | None = None,
    db_path: str = DB_PATH,
    should_stop_fn: StopCheck | None = None,
) -> dict:
    sub_id, keyword, quality_filter, media_type, sub_tmdb_id, sub_tmdb_type, sub_year, auto_transfer, min_confidence = subscription_row[:9]
    target_seasons = subscription_row[9] if len(subscription_row) > 9 else None
    min_confidence = float(min_confidence or SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE)

    subscription_dict = build_subscription_dict(
        sub_id,
        keyword,
        media_type,
        sub_tmdb_id,
        sub_tmdb_type,
        sub_year,
        target_seasons,
    )

    async def should_stop_subscription() -> bool:
        if await _should_stop(should_stop_fn):
            return True
        return not await is_subscription_still_active(sub_id, db_path)

    subscription_state = await evaluate_subscription_completion(
        subscription_dict,
        jellyfin,
        proxy_config,
    )
    if await should_stop_subscription():
        log_event("subscription.check.item_cancelled", subscription_id=sub_id, stage="completion_evaluated")
        return {"processed": 0, "submitted": 0, "skipped": 0, "pending": 0, "cancelled": True}
    if subscription_state and subscription_state.get("status") == "completed":
        log_event("subscription.check.item_completed_skip", subscription_id=sub_id)
        await mark_subscription_checked(sub_id, db_path)
        return {"processed": 0, "submitted": 0, "skipped": 0, "pending": 0}

    missing_episodes = await get_missing_subscription_episodes(subscription_dict, jellyfin, proxy_config)
    if await should_stop_subscription():
        log_event("subscription.check.item_cancelled", subscription_id=sub_id, stage="missing_episodes_loaded")
        return {"processed": 0, "submitted": 0, "skipped": 0, "pending": 0, "cancelled": True}
    if missing_episodes:
        log_event(
            "subscription.check.item_targets",
            subscription_id=sub_id,
            target_count=len(missing_episodes),
            preview=[f"S{item['season']:02d}E{item['episode']:02d}" for item in missing_episodes[:8]],
        )
    elif (sub_tmdb_type or media_type) == "tv" and sub_tmdb_id:
        log_event("subscription.check.item_no_targets", subscription_id=sub_id, tmdb_id=sub_tmdb_id)
        await mark_subscription_checked(sub_id, db_path)
        return {"processed": 0, "submitted": 0, "skipped": 0, "pending": 0}

    seen_result_links = set()
    seen_media_fingerprints = set()
    counts_total = {"processed": 0, "submitted": 0, "skipped": 0, "pending": 0}
    all_results = await search_subscription_results(subscription_dict, missing_episodes, should_stop_subscription)

    for result in all_results:
        if await should_stop_subscription():
            log_event("subscription.check.item_cancelled", subscription_id=sub_id, stage="processing_results")
            counts_total["cancelled"] = True
            return counts_total
        counts = await process_subscription_result(
            result,
            subscription_id=sub_id,
            keyword=keyword,
            subscription_year=sub_year,
            media_type=media_type,
            tmdb_id=sub_tmdb_id,
            tmdb_type=sub_tmdb_type,
            quality_filter=quality_filter,
            auto_transfer=bool(auto_transfer),
            min_confidence=min_confidence,
            jellyfin=jellyfin,
            seen_result_links=seen_result_links,
            seen_media_fingerprints=seen_media_fingerprints,
        )
        counts_total["processed"] += counts["processed"]
        counts_total["submitted"] += counts["submitted"]
        counts_total["skipped"] += counts["skipped"]
        counts_total["pending"] += counts["pending"]

    await mark_subscription_checked(sub_id, db_path)
    return counts_total
