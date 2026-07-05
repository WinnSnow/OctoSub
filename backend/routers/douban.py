# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Query, Response

from douban_client_service import DoubanClientError
from douban_service import fetch_douban_image, get_douban_detail, get_douban_recommendations, search_douban
from telegram_service import get_active_proxy_config


router = APIRouter()


@router.get("/api/douban/search")
async def douban_search(
    keyword: str = Query(..., min_length=1),
    media_type: str | None = Query(default=None, pattern="^(movie|tv)$"),
):
    return await search_douban(keyword, media_type, get_active_proxy_config())


@router.get("/api/douban/recommendations")
async def douban_recommendations(
    category: str = Query(default="movie_hot"),
    page: int = Query(default=1, ge=1),
    count: int = Query(default=30, ge=1, le=50),
):
    return await get_douban_recommendations(category, page, count, get_active_proxy_config())


@router.get("/api/douban/image")
async def douban_image(url: str = Query(..., min_length=1)):
    try:
        content, content_type = await fetch_douban_image(url, get_active_proxy_config())
    except DoubanClientError as exc:
        raise HTTPException(status_code=400 if not exc.retryable else 502, detail=exc.message) from exc
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/douban/{douban_id}")
async def douban_detail(
    douban_id: str,
    media_type: str | None = Query(default=None, pattern="^(movie|tv)$"),
):
    return await get_douban_detail(douban_id, media_type, get_active_proxy_config())
