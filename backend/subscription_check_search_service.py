# -*- coding: utf-8 -*-
import inspect
from collections.abc import Awaitable, Callable

from config import DB_PATH
from search_aggregation_service import unified_search_with_telegram_realtime
from search_match_service import estimate_search_confidence, is_search_result_relevant
from structured_logging import log_event
from subscription_lifecycle_service import build_subscription_targeted_search_terms
from subscription_repository import list_local_subscription_candidate_rows
from subscription_search_terms_service import (
    build_missing_episode_term_targets,
    build_subscription_search_terms,
    result_matches_movie_identity,
    result_matches_subscription_target,
)
from utils import classify_resource_url

StopCheck = Callable[[], bool | Awaitable[bool]]
LOCAL_SUBSCRIPTION_RESULT_LIMIT = 25


async def _should_stop(should_stop_fn: StopCheck | None) -> bool:
    if not should_stop_fn:
        return False
    result = should_stop_fn()
    if inspect.isawaitable(result):
        return bool(await result)
    return bool(result)


def _row_text(row: dict) -> str:
    return "\n".join([
        row.get("title") or "",
        row.get("description") or "",
        row.get("raw_text") or "",
    ])


def _row_has_tmdb_id(row: dict, tmdb_id: int | None) -> bool:
    if not tmdb_id:
        return False
    if str(row.get("tmdb_id") or "") == str(tmdb_id):
        return True
    return str(tmdb_id) in _row_text(row)


def _row_has_year(row: dict, year: int | None) -> bool:
    return not year or str(year) in _row_text(row) or str(row.get("year") or "") == str(year)


def _row_to_subscription_result(
    row: dict,
    *,
    keyword: str,
    year: int | None,
    tmdb_id: int | None,
    media_type: str | None,
    target_season: int | None,
    target_episode: int | None,
    search_term: str,
) -> dict | None:
    link = row.get("resource_url") or row.get("url")
    if classify_resource_url(link) != "115":
        return None
    text = _row_text(row)
    if not is_search_result_relevant(text, keyword):
        return None
    if media_type == "movie" and not result_matches_movie_identity(row, keyword, year, tmdb_id):
        return None
    if target_episode and not result_matches_subscription_target(row, target_season, target_episode):
        return None
    confidence, reason = estimate_search_confidence(text, keyword, year, media_type)
    if _row_has_tmdb_id(row, tmdb_id):
        confidence = min(0.98, confidence + 0.12)
        reason = "、".join(part for part in [reason, "TMDB匹配"] if part)
    elif _row_has_year(row, year):
        confidence = min(0.98, confidence + 0.05)
        reason = "、".join(part for part in [reason, "年份匹配"] if part)

    result = dict(row)
    result.update({
        "id": f"local:{row.get('id')}",
        "source": "local_library",
        "source_label": row.get("channel_name") or "本地资源库",
        "resource_url": link,
        "url": link,
        "link_type": classify_resource_url(link),
        "link_types": ["115"],
        "confidence": round(confidence, 2),
        "match_reason": reason or "本地资源库匹配",
        "_target_season": target_season,
        "_target_episode": target_episode,
        "_search_term": search_term,
    })
    return result


async def search_local_subscription_candidates(
    subscription: dict,
    *,
    target_season: int | None,
    target_episode: int | None,
    search_term: str,
    db_path: str | None = None,
) -> list[dict]:
    keyword = (subscription.get("keyword") or "").strip()
    if not keyword:
        return []
    year = subscription.get("year")
    tmdb_id = subscription.get("tmdb_id")
    media_type = subscription.get("tmdb_type") or subscription.get("media_type")
    rows = await list_local_subscription_candidate_rows(
        keyword,
        limit=LOCAL_SUBSCRIPTION_RESULT_LIMIT,
        db_path=db_path or DB_PATH,
    )

    candidates = []
    for row in rows:
        links = row.get("links") or []
        row["links"] = links
        if not row.get("resource_url"):
            first_115 = next((link.get("url") for link in links if classify_resource_url(link.get("url")) == "115"), None)
            if first_115:
                row["resource_url"] = first_115
        result = _row_to_subscription_result(
            row,
            keyword=keyword,
            year=year,
            tmdb_id=tmdb_id,
            media_type=media_type,
            target_season=target_season,
            target_episode=target_episode,
            search_term=search_term,
        )
        if result:
            candidates.append(result)
    return candidates


async def search_subscription_results(
    subscription: dict,
    missing_episodes: list[dict] | None = None,
    should_stop_fn: StopCheck | None = None,
) -> list[dict]:
    sub_id = subscription.get("id")
    keyword = subscription.get("keyword")
    media_type = subscription.get("media_type")
    sub_tmdb_id = subscription.get("tmdb_id")
    sub_tmdb_type = subscription.get("tmdb_type")
    sub_year = subscription.get("year")

    fallback_terms = build_subscription_search_terms(keyword, sub_year, media_type)
    search_terms = build_subscription_targeted_search_terms(
        subscription,
        missing_episodes or [],
        fallback_terms,
    )
    search_term_targets = build_missing_episode_term_targets(missing_episodes or [])

    all_results = []
    for search_term in search_terms:
        if await _should_stop(should_stop_fn):
            log_event("subscription.search.stopped", subscription_id=sub_id)
            break
        try:
            target_season, target_episode = search_term_targets.get(search_term, (None, None))
            local_results = await search_local_subscription_candidates(
                subscription,
                target_season=target_season,
                target_episode=target_episode,
                search_term=search_term,
            )
            all_results.extend(local_results)
            if local_results:
                log_event(
                    "subscription.search.local_results",
                    subscription_id=sub_id,
                    search_term=search_term,
                    count=len(local_results),
                )

            payload = await unified_search_with_telegram_realtime(
                search_term,
                selected_types={"115"},
                force_refresh=True,
                tmdb_id=sub_tmdb_id,
                tmdb_type=sub_tmdb_type or media_type,
                year=sub_year,
                season=target_season,
                episode=target_episode,
            )
            results = payload.get("results", [])
            for result in results:
                normalized_result = dict(result)
                if target_episode:
                    normalized_result["_target_season"] = target_season
                    normalized_result["_target_episode"] = target_episode
                    normalized_result["_search_term"] = search_term
                all_results.append(normalized_result)
            log_event(
                "subscription.search.remote_results",
                subscription_id=sub_id,
                search_term=search_term,
                count=len(results),
                target_season=target_season,
                target_episode=target_episode,
            )
        except Exception as exc:
            log_event(
                "subscription.search.failed",
                "warning",
                subscription_id=sub_id,
                search_term=search_term,
                error_type=type(exc).__name__,
            )

    return all_results
