# -*- coding: utf-8 -*-
"""
Jellyfin item search and provider-id query workflows.
"""
import logging
from typing import Any, Optional

from jellyfin_http_service import get_jellyfin_json
from jellyfin_match_service import (
    choose_best_item,
    coerce_int,
    find_item_by_provider_tmdb_id,
    title_variants,
)

logger = logging.getLogger(__name__)

ITEM_FIELDS = "OriginalTitle,SortName,ProviderIds"
ITEM_LIMIT = 20


async def search_item(
    base_url: str,
    headers: dict[str, str],
    name: str,
    item_type: str,
    year: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    try:
        variants = title_variants(name)
        if not variants:
            return None

        found: dict[str, dict[str, Any]] = {}
        for variant in variants:
            for include_year in ([True, False] if year else [False]):
                params: dict[str, Any] = {
                    "searchTerm": variant,
                    "IncludeItemTypes": item_type,
                    "Recursive": "true",
                    "Fields": ITEM_FIELDS,
                    "Limit": ITEM_LIMIT,
                }
                if include_year and year:
                    params["Years"] = str(year)

                data = await get_jellyfin_json(
                    base_url,
                    headers,
                    "/Items",
                    params=params,
                    default={},
                    error_message=f"搜索 {item_type} 失败",
                )
                if not isinstance(data, dict):
                    continue
                for item in data.get("Items", []):
                    item_id = item.get("Id")
                    if item_id:
                        found[item_id] = item

        if not found:
            logger.debug(f"未找到 {item_type}: {name}")
            return None

        queries = variants[:3] or [name]
        best_item, best_score = choose_best_item(list(found.values()), queries, year)
        if best_item:
            logger.debug(f"Jellyfin 匹配 {name} -> {best_item.get('Name')} ({best_score})")
            return best_item

        fallback_item = next(iter(found.values()))
        logger.debug(f"Jellyfin 搜索到候选但相似度不足: {name} -> {fallback_item.get('Name')} ({best_score})")
        return None
    except Exception as e:
        logger.error(f"搜索 {item_type} 异常: {e}")
        return None


async def search_item_by_tmdb_id(
    base_url: str,
    headers: dict[str, str],
    tmdb_id: int,
    item_type: str,
) -> Optional[dict[str, Any]]:
    try:
        tmdb_id = coerce_int(tmdb_id)
        if not tmdb_id:
            return None

        provider_filters = [str(tmdb_id), f"Tmdb.{tmdb_id}"]
        found: list[dict[str, Any]] = []
        for provider_filter in provider_filters:
            params = {
                "IncludeItemTypes": item_type,
                "Recursive": "true",
                "Fields": ITEM_FIELDS,
                "AnyProviderIdEquals": provider_filter,
                "Limit": ITEM_LIMIT,
            }
            data = await get_jellyfin_json(
                base_url,
                headers,
                "/Items",
                params=params,
                default={},
                error_message=f"按 TMDB ID 搜索 {item_type} 失败",
            )
            if isinstance(data, dict):
                found.extend(data.get("Items", []))

        matched = find_item_by_provider_tmdb_id(found, tmdb_id)
        if matched:
            logger.debug(f"Jellyfin TMDB 匹配 {item_type} {tmdb_id} -> {matched.get('Name')}")
            return matched

        logger.debug(f"未找到 {item_type} TMDB:{tmdb_id}")
        return None
    except Exception as e:
        logger.error(f"按 TMDB ID 搜索 {item_type} 异常: {e}")
        return None
