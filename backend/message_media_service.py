# -*- coding: utf-8 -*-
from douban_service import search_douban
from library_state_service import annotate_tmdb_search_items_with_jellyfin_state
from poster_service import manual_tmdb_search
from subscription_state_service import annotate_items_with_subscription_state
from telegram_service import get_active_proxy_config


async def manual_search_media_payload(keyword: str, media_type: str | None = None) -> dict:
    proxy_config = get_active_proxy_config()
    tmdb_payload = {"results": [], "available": True, "error": None}
    try:
        tmdb_payload = await manual_tmdb_search(keyword, proxy_config)
        tmdb_payload.setdefault("available", True)
        tmdb_payload.setdefault("error", None)
    except Exception:
        tmdb_payload = {
            "results": [],
            "available": False,
            "error": "TMDB 搜索失败",
        }
    douban_payload = await search_douban(keyword, media_type, proxy_config)
    douban_items = douban_payload.get("items", [])
    douban_items = await annotate_items_with_subscription_state(douban_items)
    douban_items = await annotate_tmdb_search_items_with_jellyfin_state(douban_items)
    return {
        "query": keyword,
        "tmdb": {
            "available": tmdb_payload.get("available", True),
            "error": tmdb_payload.get("error"),
            "results": tmdb_payload.get("results", []),
        },
        "douban": {
            "available": douban_payload.get("available", False),
            "error": douban_payload.get("error"),
            "results": douban_items,
            "cached": douban_payload.get("cached", False),
        },
    }
