# -*- coding: utf-8 -*-
from collections.abc import Awaitable, Callable

from poster_fetch_service import PosterMatchResult


POSTER_CACHE_SUCCESS_TTL_SECONDS = 90 * 24 * 60 * 60
POSTER_CACHE_MISS_TTL_SECONDS = 7 * 24 * 60 * 60

CacheGetFn = Callable[[str, str], Awaitable[dict | None]]


def apply_database_poster_hits(
    groups: dict[str, dict],
    existing_posters: dict[str, str],
    resolved: dict[str, PosterMatchResult],
    stats: dict,
) -> None:
    for key, group in list(groups.items()):
        candidate_keys = [key, *group.get("local_reuse_keys", [])]
        poster_url = next((existing_posters[item] for item in candidate_keys if item in existing_posters), None)
        if not poster_url:
            continue
        resolved[key] = PosterMatchResult(poster_url, "database_key_cache")
        stats["database_key_cache_hits"] += 1


async def apply_poster_cache_hits(
    groups: dict[str, dict],
    resolved: dict[str, PosterMatchResult],
    stats: dict,
    *,
    ignore_cached_misses: bool,
    get_json_cache_fn: CacheGetFn,
) -> None:
    unresolved_keys = [key for key in groups if key not in resolved]
    for key in unresolved_keys:
        payload = await get_json_cache_fn("poster_cache", f"poster:{key}")
        if not payload:
            continue
        if payload.get("miss"):
            if ignore_cached_misses:
                continue
            stats["poster_cache_hits"] += 1
            resolved[key] = PosterMatchResult(None, "poster_cache", miss=True)
        elif payload.get("poster_url"):
            stats["poster_cache_hits"] += 1
            resolved[key] = PosterMatchResult(payload["poster_url"], "poster_cache")


def build_poster_cache_payload(key: str, result: PosterMatchResult) -> dict:
    return {
        "media_key": key,
        "poster_url": result.poster_url,
        "source": result.source,
        "miss": not bool(result.poster_url),
    }


def poster_cache_ttl(result: PosterMatchResult) -> int:
    return POSTER_CACHE_SUCCESS_TTL_SECONDS if result.poster_url else POSTER_CACHE_MISS_TTL_SECONDS
