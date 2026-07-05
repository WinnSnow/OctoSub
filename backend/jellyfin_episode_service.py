# -*- coding: utf-8 -*-
"""
Jellyfin episode and season query workflows.
"""
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)


async def fetch_seasons(base_url: str, headers: dict[str, str], series_id: str) -> list[dict[str, Any]]:
    if not series_id:
        return []

    try:
        async with aiohttp.ClientSession() as session:
            url = urljoin(base_url, f"/Shows/{series_id}/Seasons")
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.error(f"获取季度列表失败: HTTP {response.status}")
                    return []
                data = await response.json()
                return data.get("Items", [])
    except Exception as e:
        logger.error(f"获取季度列表异常: {e}")
        return []


async def fetch_season_episodes(
    base_url: str,
    headers: dict[str, str],
    series_id: str,
    season_number: int,
) -> list[int]:
    try:
        seasons = await fetch_seasons(base_url, headers, series_id)
        season_id = None
        for season in seasons:
            if season.get("IndexNumber") == season_number:
                season_id = season.get("Id")
                break

        if not season_id:
            logger.debug(f"未找到第 {season_number} 季")
            return []

        async with aiohttp.ClientSession() as session:
            url = urljoin(base_url, f"/Shows/{series_id}/Episodes")
            params = {
                "SeasonId": season_id,
                "Fields": "IndexNumber",
            }
            async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.error(f"获取剧集列表失败: HTTP {response.status}")
                    return []

                data = await response.json()
                episode_numbers = []
                for episode in data.get("Items", []):
                    ep_num = episode.get("IndexNumber")
                    if ep_num is not None:
                        episode_numbers.append(ep_num)
                return sorted(episode_numbers)
    except Exception as e:
        logger.error(f"获取剧集列表异常: {e}")
        return []


async def fetch_series_episodes_by_season_id(
    base_url: str,
    headers: dict[str, str],
    series_id: str,
    season_episodes_fetcher: Callable[[int], Awaitable[list[int]]] | None = None,
) -> dict[int, list[int]]:
    try:
        seasons = await fetch_seasons(base_url, headers, series_id)
        if not seasons:
            return {}

        result: dict[int, list[int]] = {}
        for season in seasons:
            season_number = season.get("IndexNumber")
            if season_number is None or season_number == 0:
                continue
            if season_episodes_fetcher:
                result[season_number] = await season_episodes_fetcher(season_number)
            else:
                result[season_number] = await fetch_season_episodes(base_url, headers, series_id, season_number)
        return result
    except Exception as e:
        logger.error(f"获取剧集季集映射异常: {e}")
        return {}
