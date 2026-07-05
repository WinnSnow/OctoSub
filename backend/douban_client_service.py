# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from random import choice
from urllib import parse

import aiohttp

from config import (
    DOUBAN_API_KEY,
    DOUBAN_API_SECRET,
    DOUBAN_BASE_URL,
    DOUBAN_ENABLED,
    DOUBAN_TIMEOUT_SECONDS,
)
from tmdb_service import build_proxy_request_options


DOUBAN_USER_AGENTS = [
    "api-client/1 com.douban.frodo/7.22.0 Android/29 product/Mate40 vendor/HUAWEI model/Mate40 brand/HUAWEI rom/android network/wifi platform/mobile",
    "api-client/1 com.douban.frodo/7.18.0 Android/29 product/MI9 vendor/Xiaomi model/MI9 brand/Xiaomi rom/miui network/wifi platform/mobile",
    "api-client/1 com.douban.frodo/7.3.0 Android/30 product/Pixel vendor/Google model/Pixel brand/google rom/android network/wifi platform/mobile",
]


class DoubanClientError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class DoubanEndpoint:
    path: str
    params: dict


def sign_douban_request(path_or_url: str, ts: str, method: str = "GET") -> str:
    url_path = parse.urlparse(path_or_url).path or path_or_url
    raw_sign = "&".join([method.upper(), parse.quote(url_path, safe=""), ts])
    digest = hmac.new(DOUBAN_API_SECRET.encode(), raw_sign.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def build_douban_get_params(path: str, params: dict | None = None) -> dict:
    ts = (params or {}).get("_ts") or datetime.now().strftime("%Y%m%d")
    next_params = {key: value for key, value in (params or {}).items() if value is not None and key != "_ts"}
    next_params.update({
        "os_rom": "android",
        "apiKey": DOUBAN_API_KEY,
        "_ts": ts,
        "_sig": sign_douban_request(f"{DOUBAN_BASE_URL}{path}", ts),
    })
    return next_params


async def fetch_douban_json(
    path: str,
    params: dict | None = None,
    proxy_config: dict | None = None,
) -> dict:
    if not DOUBAN_ENABLED:
        raise DoubanClientError("豆瓣接入未启用", retryable=False)
    if not DOUBAN_API_KEY or not DOUBAN_API_SECRET:
        raise DoubanClientError("豆瓣 API Key 或签名密钥未配置", retryable=False)

    endpoint = path if path.startswith("/") else f"/{path}"
    connector, request_kwargs = build_proxy_request_options(proxy_config)
    timeout = aiohttp.ClientTimeout(total=DOUBAN_TIMEOUT_SECONDS)
    headers = {
        "User-Agent": choice(DOUBAN_USER_AGENTS),
        "Accept": "application/json",
    }
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
            async with session.get(
                f"{DOUBAN_BASE_URL}{endpoint}",
                params=build_douban_get_params(endpoint, params),
                **request_kwargs,
            ) as response:
                if response.status == 403:
                    raise DoubanClientError("豆瓣接口拒绝访问，可能触发风控或签名失效", status=response.status)
                if response.status == 429:
                    raise DoubanClientError("豆瓣接口请求过于频繁，请稍后重试", status=response.status)
                if response.status >= 500:
                    raise DoubanClientError("豆瓣服务暂时不可用", status=response.status)
                if response.status >= 400:
                    raise DoubanClientError("豆瓣接口请求失败", status=response.status, retryable=False)
                try:
                    return await response.json()
                except Exception as exc:
                    raise DoubanClientError("豆瓣返回的数据不是有效 JSON", retryable=True) from exc
    except DoubanClientError:
        raise
    except TimeoutError as exc:
        raise DoubanClientError("豆瓣请求超时") from exc
    except aiohttp.ClientError as exc:
        raise DoubanClientError("无法连接豆瓣接口") from exc


def douban_search_endpoint(keyword: str, start: int = 0, count: int = 20) -> DoubanEndpoint:
    return DoubanEndpoint("/search/weixin", {"q": keyword, "start": start, "count": count})


def douban_detail_endpoint(douban_id: str, media_type: str | None = None) -> DoubanEndpoint:
    media_path = "tv" if media_type == "tv" else "movie"
    return DoubanEndpoint(f"/{media_path}/{douban_id}", {})


DOUBAN_RECOMMENDATION_ENDPOINTS = {
    "movie_showing": "/subject_collection/movie_showing/items",
    "movie_soon": "/subject_collection/movie_soon/items",
    "movie_hot": "/subject_collection/movie_hot_gaia/items",
    "movie_latest": "/movie/recommend",
    "movie_top250": "/subject_collection/movie_top250/items",
    "tv_hot": "/subject_collection/tv_hot/items",
    "tv_latest": "/tv/recommend",
    "tv_weekly_chinese": "/subject_collection/tv_chinese_best_weekly/items",
    "tv_weekly_global": "/subject_collection/tv_global_best_weekly/items",
    "tv_animation": "/subject_collection/tv_animation/items",
    "tv_variety": "/subject_collection/tv_variety_show/items",
    "show_hot": "/subject_collection/show_hot/items",
}


def douban_recommendation_endpoint(category: str, page: int = 1, count: int = 30) -> DoubanEndpoint:
    normalized = (category or "movie_hot").strip().lower()
    path = DOUBAN_RECOMMENDATION_ENDPOINTS.get(normalized)
    if not path:
        raise DoubanClientError(f"不支持的豆瓣推荐分类：{category}", retryable=False)
    start = max(0, (max(1, page) - 1) * count)
    params = {"start": start, "count": count}
    if normalized in {"movie_latest", "tv_latest"}:
        params.update({"sort": "R", "tags": ""})
    return DoubanEndpoint(path, params)
