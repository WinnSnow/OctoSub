"""
搜索插件系统

借鉴 PanSou 的插件架构设计，用 Python 实现
支持异步并发搜索、智能超时控制、结果合并
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from structured_logging import log_event


class SearchResult:
    """搜索结果统一数据结构"""

    def __init__(
        self,
        unique_id: str,
        title: str,
        content: str = "",
        link: str = "",
        link_type: str = "",
        password: str = "",
        source: str = "",
        channel_name: str = "",
        publish_date: Optional[datetime] = None,
        images: List[str] = None,
    ):
        self.unique_id = unique_id
        self.title = title
        self.content = content
        self.link = link
        self.link_type = link_type
        self.password = password
        self.source = source
        self.channel_name = channel_name
        self.publish_date = publish_date or datetime.now()
        self.images = images or []

    def to_dict(self) -> dict:
        return {
            "unique_id": self.unique_id,
            "title": self.title,
            "content": self.content,
            "link": self.link,
            "link_type": self.link_type,
            "password": self.password,
            "source": self.source,
            "channel_name": self.channel_name,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "images": self.images,
        }


class SearchPlugin(ABC):
    """搜索插件基类"""

    def __init__(self, name: str, priority: int = 3, timeout: int = 10):
        """
        Args:
            name: 插件名称
            priority: 优先级 1-4，1最高
            timeout: 搜索超时时间（秒）
        """
        self.name = name
        self.priority = priority
        self.timeout = timeout

    @abstractmethod
    async def search(self, keyword: str, **kwargs) -> List[SearchResult]:
        """
        搜索接口

        Args:
            keyword: 搜索关键词
            **kwargs: 扩展参数

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        pass

    def get_priority_score(self) -> int:
        """获取优先级得分（借鉴 PanSou）"""
        priority_scores = {
            1: 1000,  # 高质量
            2: 500,   # 良好
            3: 0,     # 普通
            4: -200,  # 较低
        }
        return priority_scores.get(self.priority, 0)

    async def safe_search(self, keyword: str, **kwargs) -> List[SearchResult]:
        """
        安全搜索包装器，带超时和异常处理
        """
        try:
            return await asyncio.wait_for(
                self.search(keyword, **kwargs),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            log_event("search.plugin.timeout", "warning", plugin=self.name, timeout=self.timeout)
            return []
        except Exception as exc:
            log_event("search.plugin.failed", "warning", plugin=self.name, error_type=type(exc).__name__)
            return []


class SearchPluginManager:
    """搜索插件管理器"""

    def __init__(self):
        self.plugins: List[SearchPlugin] = []

    def register(self, plugin: SearchPlugin):
        """注册插件"""
        self.plugins.append(plugin)
        log_event("search.plugin.registered", plugin=plugin.name, priority=plugin.priority)

    async def search_all(self, keyword: str, **kwargs) -> List[SearchResult]:
        """
        并发搜索所有插件

        Args:
            keyword: 搜索关键词
            **kwargs: 扩展参数

        Returns:
            List[SearchResult]: 合并后的搜索结果
        """
        if not self.plugins:
            return []

        log_event("search.plugin.batch_started", plugin_count=len(self.plugins))

        # 并发执行所有插件
        tasks = [plugin.safe_search(keyword, **kwargs) for plugin in self.plugins]
        results_list = await asyncio.gather(*tasks)

        # 合并结果
        all_results = []
        for plugin, results in zip(self.plugins, results_list, strict=True):
            if results:
                log_event("search.plugin.results", plugin=plugin.name, result_count=len(results))
                all_results.extend(results)

        # 去重（按 link）
        seen = set()
        unique_results = []
        for result in all_results:
            if result.link and result.link not in seen:
                seen.add(result.link)
                unique_results.append(result)

        log_event("search.plugin.batch_completed", result_count=len(unique_results))
        return unique_results


# === 全局插件管理器 ===
PLUGIN_MANAGER = SearchPluginManager()


def register_plugin(plugin: SearchPlugin):
    """注册插件到全局管理器"""
    PLUGIN_MANAGER.register(plugin)
