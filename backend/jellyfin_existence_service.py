# -*- coding: utf-8 -*-
"""
Jellyfin existence-check workflows.
"""
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from jellyfin_match_service import coerce_int

logger = logging.getLogger(__name__)

SearchFn = Callable[[str, Optional[int]], Awaitable[Optional[dict[str, Any]]]]
SeasonEpisodesFn = Callable[[str, int], Awaitable[list[int]]]
SeriesEpisodesByIdFn = Callable[[str], Awaitable[dict[int, list[int]]]]


async def get_series_episodes_by_name(
    series_name: str,
    year: Optional[int],
    search_series_fn: SearchFn,
    series_episodes_by_id_fn: SeriesEpisodesByIdFn,
) -> dict[int, list[int]]:
    try:
        series = await search_series_fn(series_name, year)
        if not series:
            return {}
        return await series_episodes_by_id_fn(series.get("Id"))
    except Exception as e:
        logger.error(f"获取剧集季集映射异常: {e}")
        return {}


async def check_episode_exists(
    series_name: str,
    season: int,
    episode: int,
    year: Optional[int],
    search_series_fn: SearchFn,
    season_episodes_fn: SeasonEpisodesFn,
) -> bool:
    try:
        season = coerce_int(season)
        episode = coerce_int(episode)
        if season is None or episode is None:
            logger.debug(f"剧集季集参数无效: {series_name} season={season} episode={episode}")
            return False

        series = await search_series_fn(series_name, year)
        if not series:
            logger.debug(f"剧集不存在: {series_name}")
            return False

        existing_episodes = await season_episodes_fn(series.get("Id"), season)
        exists = episode in existing_episodes
        logger.debug(f"检查剧集 {series_name} S{season:02d}E{episode:02d}: {'存在' if exists else '不存在'}")
        return exists
    except Exception as e:
        logger.error(f"检查剧集异常: {e}")
        return False


async def check_movie_exists(
    movie_name: str,
    year: Optional[int],
    search_movie_fn: SearchFn,
) -> bool:
    try:
        movie = await search_movie_fn(movie_name, year)
        exists = movie is not None
        logger.debug(f"检查电影 {movie_name}: {'存在' if exists else '不存在'}")
        return exists
    except Exception as e:
        logger.error(f"检查电影异常: {e}")
        return False
