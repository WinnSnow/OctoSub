# -*- coding: utf-8 -*-
"""
Shared Jellyfin HTTP helpers.
"""
import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10


async def get_jellyfin_json(
    base_url: str,
    headers: dict[str, str],
    path: str,
    params: dict[str, Any] | None = None,
    default: Any = None,
    error_message: str = "Jellyfin 请求失败",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
):
    try:
        async with aiohttp.ClientSession() as session:
            url = urljoin(base_url, path)
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                if response.status != 200:
                    logger.error(f"{error_message}: HTTP {response.status}")
                    return default
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"{error_message}: {e}")
        return default
    except Exception as e:
        logger.error(f"{error_message}: {e}")
        return default


async def check_jellyfin_connection(base_url: str, headers: dict[str, str]) -> bool:
    data = await get_jellyfin_json(
        base_url,
        headers,
        "/System/Info",
        default=None,
        error_message="Jellyfin 连接失败",
    )
    if data is None:
        return False

    server_name = data.get("ServerName", "Unknown") if isinstance(data, dict) else "Unknown"
    logger.info(f"成功连接到 Jellyfin 服务器: {server_name}")
    return True


async def fetch_libraries(base_url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    libraries = await get_jellyfin_json(
        base_url,
        headers,
        "/Library/VirtualFolders",
        default=[],
        error_message="获取媒体库失败",
    )
    return libraries if isinstance(libraries, list) else []


async def fetch_library_items(
    base_url: str,
    headers: dict[str, str],
    *,
    include_item_types: str = "Movie,Series,Episode",
    page_size: int = 500,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    start_index = 0
    while True:
        data = await get_jellyfin_json(
            base_url,
            headers,
            "/Items",
            params={
                "Recursive": "true",
                "IncludeItemTypes": include_item_types,
                "Fields": "OriginalTitle,SortName,ProviderIds,ParentId,SeriesId,SeriesName,IndexNumber,ParentIndexNumber,ProductionYear",
                "StartIndex": start_index,
                "Limit": page_size,
            },
            default={},
            error_message="获取 Jellyfin 媒体项失败",
            timeout_seconds=30,
        )
        if not isinstance(data, dict):
            return items
        page_items = data.get("Items") if isinstance(data.get("Items"), list) else []
        items.extend(page_items)
        total = data.get("TotalRecordCount")
        start_index += len(page_items)
        if not page_items or not total or start_index >= int(total):
            return items
