# -*- coding: utf-8 -*-
import asyncio

import aiohttp
from fastapi import HTTPException

from config import TMDB_API_KEY
from library_state_service import annotate_tmdb_search_items_with_jellyfin_state
from poster_tmdb_client_service import normalize_manual_tmdb_result, tmdb_proxy_options
from structured_logging import log_event
from subscription_lifecycle_service import refresh_subscription_lifecycle_for_items
from subscription_state_service import annotate_items_with_subscription_state
from utils import safe_error_detail


async def manual_tmdb_search(query: str, proxy_config: dict | None = None) -> dict:
    query = query.strip()
    if not query:
        return {"results": []}

    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "zh-CN",
        "page": 1,
    }
    results = []
    try:
        connector, request_kwargs = tmdb_proxy_options(proxy_config)
        async with aiohttp.ClientSession(connector=connector) as session:
            async def search_type(url, type_name):
                async with session.get(url, params=params, **request_kwargs) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [(item, type_name) for item in data.get("results", [])]
                    return []

            movie_res, tv_res = await asyncio.gather(
                search_type("https://api.themoviedb.org/3/search/movie", "movie"),
                search_type("https://api.themoviedb.org/3/search/tv", "tv"),
            )

            for item, media_type in movie_res + tv_res:
                normalized = normalize_manual_tmdb_result(item, media_type)
                if normalized:
                    results.append(normalized)

        await refresh_subscription_lifecycle_for_items(results, proxy_config)
        results = await annotate_items_with_subscription_state(results)
        results = await annotate_tmdb_search_items_with_jellyfin_state(results)
    except Exception as exc:
        log_event("poster.manual_search_failed", "warning", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail=safe_error_detail("TMDB 搜索失败")) from exc

    return {"results": results}
