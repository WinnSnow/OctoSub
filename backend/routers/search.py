# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query

from poster_service import poster_wall_payload
from search_aggregation_service import public_search_internal, unified_search_with_telegram_realtime
from telegram_service import get_active_proxy_config


router = APIRouter()


@router.get("/")
async def read_root():
    return {"message": "Telegram Scraper API is running"}


@router.get("/api/public-search")
async def public_search(
    keyword: Annotated[str, Query(min_length=1)],
    channels: Annotated[list[str] | None, Query()] = None,
    cloud_types: Annotated[list[str] | None, Query()] = None,
    force_refresh: bool = False,
):
    return await public_search_internal(
        keyword=keyword,
        channels=channels,
        cloud_types=cloud_types,
        force_refresh=force_refresh,
    )


@router.get("/api/search")
async def unified_search(
    keyword: Annotated[str, Query(min_length=1)],
    cloud_type: Annotated[list[str] | None, Query()] = None,
    channels: Annotated[list[str] | None, Query()] = None,
    force_refresh: bool = False,
    tmdb_id: int | None = None,
    tmdb_type: str | None = None,
    year: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    sort: Annotated[
        str | None,
        Query(pattern="^(score|latest|quality|relevance|relevant|confidence)$"),
    ] = "score",
):
    payload = await unified_search_with_telegram_realtime(
        keyword=keyword,
        cloud_type=cloud_type,
        force_refresh=force_refresh,
        tmdb_id=tmdb_id,
        tmdb_type=tmdb_type,
        year=year,
        season=season,
        episode=episode,
        sort=sort,
        channels=channels,
    )
    payload["filters"].update({
        "tmdb_id": tmdb_id,
        "tmdb_type": tmdb_type,
        "season": season,
        "episode": episode,
        "sort": sort,
    })
    return payload


@router.get("/api/poster-wall")
async def poster_wall(
    category: Annotated[str, Query()] = "trending",
    provider: Annotated[str, Query()] = "tmdb",
    media_type: Annotated[str, Query(pattern="^(all|movie|tv)$")] = "all",
):
    return await poster_wall_payload(category, get_active_proxy_config(), provider, media_type)
