"""
具体搜索插件实现

实现几个常用的网盘搜索插件
"""

import re
import aiohttp
from typing import List

from search_plugins import SearchPlugin, SearchResult, register_plugin
from structured_logging import log_event


class SimpleAPIPlugin(SearchPlugin):
    """简单网盘搜索插件 - 调用公开 API"""

    def __init__(self):
        super().__init__(name="simplepan", priority=2, timeout=10)

    async def search(self, keyword: str, **kwargs) -> List[SearchResult]:
        """搜索网盘资源"""
        results = []

        # 方案1：调用 alipansou.com API (阿里云盘搜索)
        try:
            url = "https://www.alipansou.com/search"
            params = {"k": keyword, "page": 1}

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.alipansou.com/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                    if response.status == 200:
                        html = await response.text()
                        # 简单解析（提取链接）
                        links = re.findall(r'(https://www\.alipan\.com/s/[A-Za-z0-9]+)', html)
                        titles = re.findall(r'<div class="name">(.*?)</div>', html, re.S)

                        for idx, (link, title) in enumerate(zip(links[:10], titles[:10], strict=False)):
                            title = re.sub(r'<.*?>', '', title).strip()
                            results.append(SearchResult(
                                unique_id=f"alipan-{idx}",
                                title=title or f"{keyword} 资源",
                                content="阿里云盘搜索结果",
                                link=link,
                                link_type="aliyun",
                                password="",
                                source=f"plugin:{self.name}",
                            ))
        except Exception as exc:
            log_event("search.plugin.alipan_failed", "warning", plugin=self.name, error_type=type(exc).__name__)

        # 方案2：如果还是搜不到，返回占位数据（至少保证有结果）
        if not results:
            results = [
                SearchResult(
                    unique_id="placeholder-1",
                    title=f"【网盘插件】{keyword} - 正在开发中",
                    content="网盘搜索插件正在完善中，暂时返回占位数据。需要实际网站 API 或部署 PanSou 服务。",
                    link="https://example.com/placeholder",
                    link_type="other",
                    password="",
                    source=f"plugin:{self.name}",
                )
            ]

        return results


# === 注册插件 ===
register_plugin(SimpleAPIPlugin())
