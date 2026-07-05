# -*- coding: utf-8 -*-
import asyncio

import aiohttp

from config import TMDB_API_KEY, TMDB_SEARCH_TIMEOUT_SECONDS
from poster_manual_search_service import manual_tmdb_search as manual_tmdb_search
from poster_tmdb_client_service import poster_url_from_path, tmdb_proxy_options
from poster_title_service import build_poster_search_queries, parse_poster_search_identity
from poster_wall_service import (
    build_douban_poster_wall,
    build_subscription_poster_wall,
    build_tmdb_poster_wall,
    load_cached_poster_wall,
    normalize_wall_media_type,
)
from structured_logging import log_event


__all__ = [
    "fetch_movie_poster",
    "manual_tmdb_search",
    "poster_url_from_path",
    "poster_wall_payload",
]


async def fetch_movie_poster(
    movie_title: str,
    proxy_config: dict | None = None,
    media_type: str | None = None,
) -> str | None:
    if not movie_title or not TMDB_API_KEY:
        return None

    search_types = [media_type] if media_type in {"movie", "tv"} else ["movie", "tv"]
    connector, request_kwargs = tmdb_proxy_options(proxy_config)
    timeout = aiohttp.ClientTimeout(total=TMDB_SEARCH_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        async def search_one(search_type: str, query_title: str, query_year=None):
            params = {
                "api_key": TMDB_API_KEY,
                "query": query_title,
                "language": "zh-CN",
                "page": 1,
            }
            if query_year:
                year_param = "primary_release_year" if search_type == "movie" else "first_air_date_year"
                params[year_param] = query_year

            url = f"https://api.themoviedb.org/3/search/{search_type}"
            async with session.get(url, params=params, **request_kwargs) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                if data.get("results") and data["results"][0].get("poster_path"):
                    return poster_url_from_path(data["results"][0]["poster_path"])
                return None

        async def execute_tmdb_search(query_title, query_year=None):
            try:
                tasks = [search_one(search_type, query_title, query_year) for search_type in search_types]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        log_event("poster.tmdb_search_failed", "warning", error_type=type(result).__name__)
                        continue
                    if result:
                        return result
            except Exception as exc:
                log_event("poster.tmdb_search_failed", "warning", error_type=type(exc).__name__)
            return None

        identity = parse_poster_search_identity(movie_title)
        log_event(
            "poster.match_started",
            year=identity.year,
            source=identity.source,
            media_type=media_type,
            search_type_count=len(search_types),
        )

        for query in build_poster_search_queries(identity.title, identity.year):
            poster = await execute_tmdb_search(query.title, query.year)
            if poster:
                return poster

        return None


async def poster_wall_payload(
    category: str,
    proxy_config: dict | None = None,
    provider: str = "tmdb",
    media_type: str = "all",
) -> dict:
    category = category.strip().lower()
    provider = (provider or "tmdb").strip().lower()
    media_type = normalize_wall_media_type(media_type)
    if category != "subscriptions":
        cached = await load_cached_poster_wall(category, proxy_config, provider, media_type)
        if cached:
            return cached

    if category == "subscriptions":
        return await build_subscription_poster_wall(proxy_config)

    if provider == "douban":
        return await build_douban_poster_wall(category, proxy_config)

    if provider != "tmdb":
        return {
            "provider": provider,
            "category": category,
            "media_type": media_type,
            "items": [],
            "cached": False,
            "available": False,
            "error": "该推荐来源暂未接入",
        }

    return await build_tmdb_poster_wall(category, proxy_config, media_type)
