# -*- coding: utf-8 -*-
"""
Jellyfin API 客户端
用于查询 Jellyfin 媒体库，检查剧集和电影是否已存在
"""
from typing import Optional, List, Dict, Any

from jellyfin_existence_service import (
    check_episode_exists as check_episode_exists_workflow,
    check_movie_exists as check_movie_exists_workflow,
    get_series_episodes_by_name,
)
from jellyfin_episode_service import (
    fetch_season_episodes,
    fetch_series_episodes_by_season_id,
)
from jellyfin_http_service import check_jellyfin_connection, fetch_libraries, fetch_library_items
from jellyfin_item_query_service import search_item, search_item_by_tmdb_id
from jellyfin_match_service import (
    coerce_int,
    normalize_title,
    score_item,
    title_variants,
)


def _coerce_int(value) -> Optional[int]:
    return coerce_int(value)


class JellyfinClient:
    """Jellyfin API 客户端"""

    def __init__(self, base_url: str, api_key: str):
        """
        初始化 Jellyfin 客户端

        Args:
            base_url: Jellyfin 服务器地址 (如 http://192.168.1.100:8096)
            api_key: Jellyfin API 密钥
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-Emby-Token': api_key,
            'Content-Type': 'application/json'
        }

    @staticmethod
    def _normalize_title(value: Optional[str]) -> str:
        return normalize_title(value)

    @classmethod
    def _title_variants(cls, name: str) -> List[str]:
        return title_variants(name)

    @classmethod
    def _score_item(cls, item: Dict[str, Any], query: str, year: Optional[int]) -> int:
        return score_item(item, query, year)

    async def _search_item(self, name: str, item_type: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return await search_item(self.base_url, self.headers, name, item_type, year)

    async def _search_item_by_tmdb_id(self, tmdb_id: int, item_type: str) -> Optional[Dict[str, Any]]:
        return await search_item_by_tmdb_id(self.base_url, self.headers, tmdb_id, item_type)

    async def test_connection(self) -> bool:
        """
        测试 Jellyfin 连接

        Returns:
            bool: 连接成功返回 True，否则返回 False
        """
        return await check_jellyfin_connection(self.base_url, self.headers)

    async def search_series(self, name: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        搜索剧集

        Args:
            name: 剧集名称
            year: 年份（可选）

        Returns:
            dict: 剧集信息，如果未找到返回 None
            {
                'Id': 'series_id',
                'Name': '剧集名',
                'ProductionYear': 2024,
                'Type': 'Series'
            }
        """
        return await self._search_item(name, 'Series', year)

    async def search_series_by_tmdb_id(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        return await self._search_item_by_tmdb_id(tmdb_id, 'Series')

    async def search_movie(self, name: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        搜索电影

        Args:
            name: 电影名称
            year: 年份（可选）

        Returns:
            dict: 电影信息，如果未找到返回 None
        """
        return await self._search_item(name, 'Movie', year)

    async def search_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        return await self._search_item_by_tmdb_id(tmdb_id, 'Movie')

    async def get_season_episodes(self, series_id: str, season_number: int) -> List[int]:
        """
        获取指定季度的已有集数列表

        Args:
            series_id: 剧集 ID
            season_number: 季数

        Returns:
            list: 集数列表，如 [1, 2, 3, 4, 5]
        """
        return await fetch_season_episodes(self.base_url, self.headers, series_id, season_number)

    async def get_series_episodes_by_season_id(self, series_id: str) -> Dict[int, List[int]]:
        """
        按 Jellyfin 剧集 ID 获取已有的季集映射。

        Returns:
            dict: {season_number: [episode_numbers]}
        """
        return await fetch_series_episodes_by_season_id(
            self.base_url,
            self.headers,
            series_id,
            lambda season_number: self.get_season_episodes(series_id, season_number),
        )

    async def get_series_episodes_by_season(self, series_name: str, year: Optional[int] = None) -> Dict[int, List[int]]:
        """
        获取剧集在 Jellyfin 中已有的季集映射。

        Returns:
            dict: {season_number: [episode_numbers]}
        """
        return await get_series_episodes_by_name(
            series_name,
            year,
            self.search_series,
            self.get_series_episodes_by_season_id,
        )

    async def check_episode_exists(self, series_name: str, season: int, episode: int, year: Optional[int] = None) -> bool:
        """
        检查指定剧集是否存在

        Args:
            series_name: 剧集名称
            season: 季数
            episode: 集数
            year: 年份（可选）

        Returns:
            bool: 存在返回 True，不存在返回 False
        """
        return await check_episode_exists_workflow(
            series_name,
            season,
            episode,
            year,
            self.search_series,
            self.get_season_episodes,
        )

    async def check_movie_exists(self, movie_name: str, year: Optional[int] = None) -> bool:
        """
        检查电影是否存在

        Args:
            movie_name: 电影名称
            year: 年份（可选）

        Returns:
            bool: 存在返回 True，不存在返回 False
        """
        return await check_movie_exists_workflow(movie_name, year, self.search_movie)

    async def get_libraries(self) -> List[Dict[str, Any]]:
        """
        获取所有媒体库列表

        Returns:
            list: 媒体库列表
        """
        return await fetch_libraries(self.base_url, self.headers)

    async def get_library_items(self) -> List[Dict[str, Any]]:
        """
        获取 Jellyfin 全库中可用于本地入库索引的电影、剧集和分集。
        """
        return await fetch_library_items(self.base_url, self.headers)


# 全局 Jellyfin 客户端实例
_jellyfin_client: Optional[JellyfinClient] = None


def init_jellyfin_client(base_url: str, api_key: str) -> JellyfinClient:
    """
    初始化全局 Jellyfin 客户端

    Args:
        base_url: Jellyfin 服务器地址
        api_key: API 密钥

    Returns:
        JellyfinClient: 客户端实例
    """
    global _jellyfin_client
    _jellyfin_client = JellyfinClient(base_url, api_key)
    return _jellyfin_client


def get_jellyfin_client() -> Optional[JellyfinClient]:
    """
    获取全局 Jellyfin 客户端实例

    Returns:
        JellyfinClient: 客户端实例，如果未初始化返回 None
    """
    return _jellyfin_client
