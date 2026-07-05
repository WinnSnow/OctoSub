# -*- coding: utf-8 -*-
from random import choice
from urllib.parse import quote, urlparse

import aiohttp

from cache_service import get_json_cache, set_json_cache
from config import (
    DOUBAN_DETAIL_TTL_SECONDS,
    DOUBAN_RECOMMENDATION_TTL_SECONDS,
    DOUBAN_SEARCH_TTL_SECONDS,
    DOUBAN_TIMEOUT_SECONDS,
)
from douban_client_service import (
    DOUBAN_RECOMMENDATION_ENDPOINTS,
    DOUBAN_USER_AGENTS,
    DoubanClientError,
    douban_detail_endpoint,
    douban_recommendation_endpoint,
    douban_search_endpoint,
    fetch_douban_json,
)
from tmdb_service import build_proxy_request_options


DOUBAN_IMAGE_MAX_BYTES = 8 * 1024 * 1024


def normalize_douban_media_type(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if normalized in {"tv", "movie"}:
        return normalized
    if normalized in {"电视剧", "剧集"}:
        return "tv"
    if normalized in {"电影"}:
        return "movie"
    return None


def is_douban_image_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    return host == "doubanio.com" or host.endswith(".doubanio.com")


def proxied_douban_image_url(url: str | None) -> str | None:
    if not is_douban_image_url(url):
        return url
    return f"/api/douban/image?url={quote(url, safe='')}"


def _image_url_from_douban(item: dict) -> str | None:
    for path in (
        ("pic", "large"),
        ("pic", "normal"),
        ("cover", "url"),
        ("cover", "image", "normal", "url"),
        ("cover", "image", "large", "url"),
    ):
        current = item
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current:
            return current
    return item.get("cover_url")


def _rating_value(item: dict) -> float | None:
    rating = item.get("rating")
    if isinstance(rating, dict):
        value = rating.get("value")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _rating_count(item: dict) -> int | None:
    rating = item.get("rating")
    if isinstance(rating, dict):
        for key in ("count", "people_count", "numRaters", "rating_people"):
            value = rating.get(key)
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                continue
    for key in ("rating_count", "comments_count", "votes_count"):
        value = item.get(key)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


def _year_value(item: dict) -> int | None:
    year = item.get("year")
    if isinstance(year, int):
        return year
    if isinstance(year, str) and year[:4].isdigit():
        return int(year[:4])
    for key in ("release_date", "pubdate"):
        value = item.get(key)
        if isinstance(value, str) and value[:4].isdigit():
            return int(value[:4])
        if isinstance(value, list):
            for candidate in value:
                if isinstance(candidate, str) and candidate[:4].isdigit():
                    return int(candidate[:4])
    return None


def _people_names(items: list | None) -> list[str]:
    names = []
    for item in items or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(item["name"])
    return names


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("title")
                if name:
                    result.append(str(name).strip())
        return result
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.replace("/", ",").split(",") if part.strip()]
    return []


def _first_text_value(item: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            first = next((candidate for candidate in value if isinstance(candidate, str) and candidate.strip()), None)
            if first:
                return first.strip()
    return None


def normalize_douban_item(item: dict | None, fallback_type: str | None = None) -> dict | None:
    if not isinstance(item, dict):
        return None
    target = item.get("target") if isinstance(item.get("target"), dict) else item
    outer_type = item.get("target_type") if target is not item else None
    media_type = normalize_douban_media_type(
        target.get("type")
        or target.get("subtype")
        or target.get("type_name")
        or outer_type
        or fallback_type
    )
    if media_type not in {"movie", "tv"}:
        return None

    douban_id = target.get("id")
    title = target.get("title") or target.get("name")
    if not douban_id or not title:
        return None

    year = _year_value(target)
    original_poster_url = _image_url_from_douban(target)
    poster_url = proxied_douban_image_url(original_poster_url)
    url = target.get("url") or target.get("sharing_url") or f"https://movie.douban.com/subject/{douban_id}/"
    rating = _rating_value(target)
    summary = target.get("intro") or target.get("summary") or target.get("abstract") or ""
    original_title = target.get("original_title") or target.get("latin_title") or ""
    aliases = _string_list(target.get("aka") or target.get("aka_names") or target.get("aliases"))
    pubdates = _string_list(target.get("pubdate") or target.get("pubdates") or target.get("release_date"))
    durations = _string_list(target.get("durations") or target.get("duration"))
    countries = _string_list(target.get("countries") or target.get("regions"))
    languages = _string_list(target.get("languages") or target.get("language"))
    search_keyword = f"{title} {year}" if year else title

    return {
        "source": "douban",
        "provider": "douban",
        "provider_id": str(douban_id),
        "douban_id": str(douban_id),
        "douban_url": url,
        "douban_rating": rating,
        "douban_rating_count": _rating_count(target),
        "title": title,
        "original_title": original_title,
        "aliases": aliases,
        "media_type": media_type,
        "tmdb_type": media_type,
        "year": year,
        "pubdate": _first_text_value(target, ("mainland_pubdate", "pubdate", "release_date")),
        "pubdates": pubdates,
        "durations": durations,
        "countries": countries,
        "languages": languages,
        "episode_count": target.get("episodes_count") or target.get("episode_count") or target.get("episodes"),
        "poster_url": poster_url,
        "original_poster_url": original_poster_url,
        "overview": summary,
        "summary": summary,
        "genres": target.get("genres") or [],
        "directors": _people_names(target.get("directors")),
        "writers": _people_names(target.get("writers") or target.get("screenwriters")),
        "actors": _people_names(target.get("actors")),
        "url": url,
        "search_keyword": search_keyword,
        "metadata_source": "douban",
    }


async def fetch_douban_image(url: str, proxy_config: dict | None = None) -> tuple[bytes, str]:
    if not is_douban_image_url(url):
        raise DoubanClientError("不允许代理该图片地址", retryable=False)

    connector, request_kwargs = build_proxy_request_options(proxy_config)
    timeout = aiohttp.ClientTimeout(total=DOUBAN_TIMEOUT_SECONDS)
    headers = {
        "User-Agent": choice(DOUBAN_USER_AGENTS),
        "Referer": "https://movie.douban.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=False, **request_kwargs) as response:
                if response.status >= 400:
                    raise DoubanClientError(f"豆瓣图片读取失败（HTTP {response.status}）", status=response.status)
                content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                if not content_type.startswith("image/"):
                    raise DoubanClientError("豆瓣图片返回的内容类型无效", retryable=True)
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > DOUBAN_IMAGE_MAX_BYTES:
                    raise DoubanClientError("豆瓣图片过大，已拒绝代理", retryable=False)
                content = await response.read()
                if len(content) > DOUBAN_IMAGE_MAX_BYTES:
                    raise DoubanClientError("豆瓣图片过大，已拒绝代理", retryable=False)
                return content, content_type
    except DoubanClientError:
        raise
    except TimeoutError as exc:
        raise DoubanClientError("豆瓣图片请求超时") from exc
    except aiohttp.ClientError as exc:
        raise DoubanClientError("无法连接豆瓣图片服务") from exc


def _ok_payload(items: list[dict], **extra) -> dict:
    return {
        "available": True,
        "error": None,
        "items": items,
        **extra,
    }


def _error_payload(exc: Exception, **extra) -> dict:
    message = exc.message if isinstance(exc, DoubanClientError) else "豆瓣数据获取失败"
    return {
        "available": False,
        "error": message,
        "items": [],
        **extra,
    }


async def search_douban(keyword: str, media_type: str | None = None, proxy_config: dict | None = None) -> dict:
    keyword = (keyword or "").strip()
    selected_type = normalize_douban_media_type(media_type)
    if not keyword:
        return _ok_payload([], query=keyword, media_type=selected_type)
    cache_key = f"douban:search:{selected_type or 'all'}:{keyword}"
    cached = await get_json_cache("douban_cache", cache_key)
    if cached:
        return cached
    try:
        endpoint = douban_search_endpoint(keyword)
        data = await fetch_douban_json(endpoint.path, endpoint.params, proxy_config)
        raw_items = data.get("items") or data.get("results") or data.get("subjects") or []
        items = []
        for raw in raw_items:
            item = normalize_douban_item(raw)
            if item and (not selected_type or item["media_type"] == selected_type):
                items.append(item)
        payload = _ok_payload(items, query=keyword, media_type=selected_type, cached=False)
        await set_json_cache("douban_cache", cache_key, payload, DOUBAN_SEARCH_TTL_SECONDS)
        return payload
    except Exception as exc:
        return _error_payload(exc, query=keyword, media_type=selected_type, cached=False)


async def get_douban_detail(douban_id: str, media_type: str | None = None, proxy_config: dict | None = None) -> dict:
    douban_id = str(douban_id or "").strip()
    selected_type = normalize_douban_media_type(media_type)
    if not douban_id:
        return _error_payload(DoubanClientError("豆瓣 ID 不能为空", retryable=False), media_type=selected_type)
    cache_key = f"douban:detail:{selected_type or 'unknown'}:{douban_id}"
    cached = await get_json_cache("douban_cache", cache_key)
    if cached:
        return cached
    types_to_try = [selected_type] if selected_type else ["movie", "tv"]
    last_error: Exception | None = None
    for candidate_type in types_to_try:
        try:
            endpoint = douban_detail_endpoint(douban_id, candidate_type)
            data = await fetch_douban_json(endpoint.path, endpoint.params, proxy_config)
            item = normalize_douban_item(data, candidate_type)
            if item:
                payload = {
                    "available": True,
                    "error": None,
                    "item": item,
                    "items": [item],
                    "media_type": item["media_type"],
                    "cached": False,
                }
                await set_json_cache("douban_cache", cache_key, payload, DOUBAN_DETAIL_TTL_SECONDS)
                return payload
        except Exception as exc:
            last_error = exc
            continue
    return _error_payload(last_error or DoubanClientError("未找到豆瓣条目", retryable=False), media_type=selected_type, cached=False)


async def get_douban_recommendations(
    category: str,
    page: int = 1,
    count: int = 30,
    proxy_config: dict | None = None,
) -> dict:
    normalized_category = (category or "movie_hot").strip().lower()
    if normalized_category not in DOUBAN_RECOMMENDATION_ENDPOINTS:
        return _error_payload(
            DoubanClientError(f"不支持的豆瓣推荐分类：{category}", retryable=False),
            category=normalized_category,
            cached=False,
        )
    bounded_count = max(1, min(int(count or 30), 50))
    bounded_page = max(1, int(page or 1))
    cache_key = f"douban:recommend:{normalized_category}:{bounded_page}:{bounded_count}"
    cached = await get_json_cache("douban_cache", cache_key)
    if cached:
        return cached
    try:
        endpoint = douban_recommendation_endpoint(normalized_category, bounded_page, bounded_count)
        data = await fetch_douban_json(endpoint.path, endpoint.params, proxy_config)
        fallback_type = "tv" if normalized_category.startswith("tv_") else "movie"
        raw_items = data.get("subject_collection_items") or data.get("items") or data.get("subjects") or []
        items = [item for item in (normalize_douban_item(raw, fallback_type) for raw in raw_items) if item]
        payload = _ok_payload(
            items,
            provider="douban",
            category=normalized_category,
            media_type=fallback_type,
            cached=False,
        )
        await set_json_cache("douban_cache", cache_key, payload, DOUBAN_RECOMMENDATION_TTL_SECONDS)
        return payload
    except Exception as exc:
        return _error_payload(exc, provider="douban", category=normalized_category, cached=False)
