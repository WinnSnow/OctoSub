# -*- coding: utf-8 -*-
import aiosqlite

from cache_service import get_json_cache, set_json_cache
from config import DB_PATH
from douban_service import get_douban_recommendations
from library_state_service import annotate_tmdb_search_items_with_jellyfin_state
from subscription_lifecycle_service import (
    refresh_subscription_lifecycle_for_ids,
    refresh_subscription_lifecycle_for_items,
)
from subscription_state_service import (
    annotate_items_with_subscription_state,
    build_subscription_state_payload,
    strip_live_state_from_items,
)
from tmdb_service import fetch_tmdb_json, normalize_tmdb_wall_item


POSTER_WALL_ENDPOINT_MAP = {
    ("trending", "all"): ("trending/all/week", None),
    ("trending", "movie"): ("trending/movie/week", "movie"),
    ("trending", "tv"): ("trending/tv/week", "tv"),
    ("popular", "all"): ("trending/all/day", None),
    ("popular", "movie"): ("movie/popular", "movie"),
    ("popular", "tv"): ("tv/popular", "tv"),
    ("now_playing", "all"): ("movie/now_playing", "movie"),
    ("now_playing", "movie"): ("movie/now_playing", "movie"),
    ("now_playing", "tv"): ("tv/on_the_air", "tv"),
    ("on_the_air", "all"): ("tv/on_the_air", "tv"),
    ("on_the_air", "movie"): ("movie/now_playing", "movie"),
    ("on_the_air", "tv"): ("tv/on_the_air", "tv"),
}


def normalize_wall_media_type(media_type: str | None = None) -> str:
    normalized = (media_type or "all").strip().lower()
    return normalized if normalized in {"all", "movie", "tv"} else "all"


def poster_wall_cache_key(provider: str, category: str, media_type: str) -> str:
    return f"poster-wall:{provider}:{category}:{media_type}"


def with_provider_metadata(item: dict, provider: str) -> dict:
    if provider != "tmdb":
        return item
    tmdb_id = item.get("tmdb_id")
    tmdb_type = item.get("tmdb_type")
    return {
        **item,
        "provider": "tmdb",
        "provider_id": tmdb_id,
        "media_type": tmdb_type,
    }


async def build_douban_poster_wall(
    category: str,
    proxy_config: dict | None = None,
) -> dict:
    payload = await get_douban_recommendations(category, 1, 40, proxy_config)
    if not payload.get("available"):
        return {
            "provider": "douban",
            "category": category,
            "media_type": payload.get("media_type") or "all",
            "items": [],
            "cached": payload.get("cached", False),
            "available": False,
            "error": payload.get("error") or "豆瓣推荐暂不可用",
        }
    items = payload.get("items", [])[:40]
    return {
        "provider": "douban",
        "category": category,
        "media_type": payload.get("media_type") or "all",
        "items": await annotate_poster_wall_items(items, proxy_config),
        "cached": payload.get("cached", False),
        "available": True,
        "error": None,
    }


async def annotate_poster_wall_items(items: list[dict], proxy_config: dict | None = None) -> list[dict]:
    await refresh_subscription_lifecycle_for_items(items, proxy_config)
    items = await annotate_items_with_subscription_state(items)
    items = await annotate_tmdb_search_items_with_jellyfin_state(items)
    return items


async def load_cached_poster_wall(
    category: str,
    proxy_config: dict | None = None,
    provider: str = "tmdb",
    media_type: str = "all",
) -> dict | None:
    cached = await get_json_cache("poster_cache", poster_wall_cache_key(provider, category, media_type))
    if not cached:
        return None

    cached = strip_live_state_from_items(cached)
    cached["items"] = await annotate_poster_wall_items(cached.get("items", []), proxy_config)
    return cached


async def build_subscription_poster_wall(proxy_config: dict | None = None, db_path: str = DB_PATH) -> dict:
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(
            """
            SELECT id, keyword, media_type, tmdb_id, tmdb_type, year, poster_url,
                   enabled, status, completed_at, progress_current, progress_total
            FROM subscriptions
            WHERE poster_url IS NOT NULL AND poster_url != ''
            ORDER BY id DESC
            LIMIT 60
            """
        ) as cursor:
            rows = await cursor.fetchall()

    items = [{
        "subscription_id": row[0],
        "title": row[1],
        "tmdb_type": row[4] or row[2],
        "tmdb_id": row[3],
        "year": row[5],
        "poster_url": row[6],
        "search_keyword": f"{row[1]} {row[5]}" if row[5] else row[1],
        "subscription_state": build_subscription_state_payload({
            "id": row[0],
            "keyword": row[1],
            "media_type": row[2],
            "tmdb_id": row[3],
            "tmdb_type": row[4],
            "year": row[5],
            "poster_url": row[6],
            "enabled": bool(row[7]),
            "status": row[8],
            "completed_at": row[9],
            "progress_current": row[10],
            "progress_total": row[11],
        }),
    } for row in rows]

    await refresh_subscription_lifecycle_for_ids({row[0] for row in rows}, proxy_config)
    items = await annotate_items_with_subscription_state(items)
    items = await annotate_tmdb_search_items_with_jellyfin_state(items)
    return {
        "provider": "local",
        "category": "subscriptions",
        "media_type": "all",
        "items": items,
        "cached": False,
    }


async def build_tmdb_poster_wall(
    category: str,
    proxy_config: dict | None = None,
    media_type: str = "all",
) -> dict:
    media_type = normalize_wall_media_type(media_type)
    endpoint, fallback_type = POSTER_WALL_ENDPOINT_MAP.get(
        (category, media_type),
        POSTER_WALL_ENDPOINT_MAP[("trending", "all")],
    )
    data = await fetch_tmdb_json(endpoint, {"page": 1}, proxy_config)

    items = []
    for item in data.get("results", []):
        normalized = normalize_tmdb_wall_item(item, fallback_type)
        if normalized:
            items.append(with_provider_metadata(normalized, "tmdb"))

    payload = {
        "provider": "tmdb",
        "category": category,
        "media_type": media_type,
        "items": await annotate_poster_wall_items(items[:40], proxy_config),
        "cached": False,
    }
    await set_json_cache(
        "poster_cache",
        poster_wall_cache_key("tmdb", category, media_type),
        strip_live_state_from_items(payload),
        3600,
    )
    return payload
