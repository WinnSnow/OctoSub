# -*- coding: utf-8 -*-
import asyncio
import json
import time

from fastapi import HTTPException

from config import (
    PUBLIC_SEARCH_CHANNELS,
    PUBLIC_SEARCH_MAX_CHANNELS,
    PUBLIC_SEARCH_TIMEOUT_SECONDS,
    PUBLIC_SEARCH_TTL_SECONDS,
    SEARCH_DEFAULT_CLOUD_TYPE,
)
from public_search_service import fetch_public_channel_search, get_default_public_channels
from search_service import unified_search_internal
from structured_logging import log_event
from utils import normalize_channel_url, normalize_cloud_types

try:
    from search_plugins import PLUGIN_MANAGER
    import search_plugins_impl  # noqa: F401
    PLUGIN_SEARCH_ENABLED = True
except Exception as exc:
    PLUGIN_MANAGER = None
    PLUGIN_SEARCH_ENABLED = False
    log_event("search.plugin.load_failed", "warning", error_type=type(exc).__name__)


PUBLIC_SEARCH_CACHE: dict[str, dict] = {}
GLOBAL_PROXY_CONFIG = None


def set_global_proxy_config(proxy_config: dict | None) -> None:
    global GLOBAL_PROXY_CONFIG
    GLOBAL_PROXY_CONFIG = proxy_config


async def search_telegram_realtime_internal(
    keyword: str,
    channels: list[str] | None = None,
    selected_types: set[str] | None = None,
) -> list[dict]:
    try:
        selected_channels = [
            normalize_channel_url(item)
            for item in (channels or PUBLIC_SEARCH_CHANNELS)
            if normalize_channel_url(item)
        ][:PUBLIC_SEARCH_MAX_CHANNELS]
        if not selected_channels:
            return []

        selected_types = selected_types or normalize_cloud_types(None)
        tasks = [
            fetch_public_channel_search(
                channel,
                keyword.strip(),
                selected_types,
                GLOBAL_PROXY_CONFIG,
                PUBLIC_SEARCH_TIMEOUT_SECONDS,
            )
            for channel in selected_channels
        ]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for item in settled:
            if isinstance(item, Exception):
                continue
            results.extend(item.get("results", []))

        results.sort(key=lambda x: x.get("publish_date") or "", reverse=True)
        log_event("search.realtime.completed", result_count=len(results), channel_count=len(selected_channels))
        return results
    except Exception as exc:
        log_event("search.realtime.failed", "warning", error_type=type(exc).__name__)
        return []


async def public_search_internal(
    keyword: str,
    channels: list[str] | None = None,
    cloud_types: list[str] | None = None,
    force_refresh: bool = False,
) -> dict:
    started = time.perf_counter()
    selected_channels = channels or await get_default_public_channels()
    selected_channels = [normalize_channel_url(item) for item in selected_channels if normalize_channel_url(item)]
    selected_channels = selected_channels[:PUBLIC_SEARCH_MAX_CHANNELS]
    if not selected_channels:
        raise HTTPException(status_code=400, detail="请先配置至少一个公开频道")

    selected_types = normalize_cloud_types(cloud_types)
    cache_key = json.dumps({
        "keyword": keyword.strip(),
        "channels": sorted(selected_channels),
        "cloud_types": sorted(selected_types),
    }, ensure_ascii=False, sort_keys=True)
    cached = PUBLIC_SEARCH_CACHE.get(cache_key)
    if cached and not force_refresh and time.time() - cached["created_at"] < PUBLIC_SEARCH_TTL_SECONDS:
        payload = dict(cached["payload"])
        payload["cached"] = True
        return payload

    all_tasks = [
        fetch_public_channel_search(
            channel,
            keyword.strip(),
            selected_types,
            GLOBAL_PROXY_CONFIG,
            PUBLIC_SEARCH_TIMEOUT_SECONDS,
        )
        for channel in selected_channels
    ]

    plugin_task_index = len(all_tasks)
    if PLUGIN_SEARCH_ENABLED and PLUGIN_MANAGER is not None:
        async def search_plugins_wrapper():
            try:
                plugin_results = await PLUGIN_MANAGER.search_all(keyword.strip())
                converted = []
                for pr in plugin_results:
                    converted.append({
                        "title": pr.title,
                        "raw_text": pr.content,
                        "link": pr.link,
                        "link_type": pr.link_type,
                        "password": pr.password,
                        "channel_name": pr.source,
                        "publish_date": pr.publish_date.isoformat() if pr.publish_date else None,
                    })
                return {"source": "plugin", "results": converted}
            except Exception as exc:
                log_event("search.plugin.wrapper_failed", "warning", error_type=type(exc).__name__)
                return {"source": "plugin", "results": []}

        all_tasks.append(search_plugins_wrapper())

    settled = await asyncio.gather(*all_tasks, return_exceptions=True)

    results = []
    failed_channels = []
    plugin_results = []

    for channel, item in zip(selected_channels, settled[:len(selected_channels)], strict=True):
        if isinstance(item, Exception):
            failed_channels.append({"channel": channel, "error": str(item)})
        else:
            results.extend(item["results"])

    if PLUGIN_SEARCH_ENABLED and len(settled) > plugin_task_index:
        plugin_result = settled[plugin_task_index]
        if isinstance(plugin_result, dict):
            plugin_results = plugin_result.get("results", [])
            results.extend(plugin_results)

    results.sort(key=lambda item: item.get("publish_date") or "", reverse=True)
    payload = {
        "results": results,
        "total": len(results),
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "source": "public_realtime",
        "failed_channels": failed_channels,
        "plugin_count": len(plugin_results) if PLUGIN_SEARCH_ENABLED else 0,
        "filters": {
            "keyword": keyword.strip(),
            "channels": selected_channels,
            "cloud_types": sorted(selected_types),
        },
        "cached": False,
    }
    PUBLIC_SEARCH_CACHE[cache_key] = {"created_at": time.time(), "payload": payload}
    return payload


async def unified_search_with_telegram_realtime(
    keyword: str,
    cloud_type: list[str] | None = None,
    selected_types: set[str] | None = None,
    force_refresh: bool = False,
    tmdb_id: int | None = None,
    tmdb_type: str | None = None,
    year: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    sort: str | None = None,
    channels: list[str] | None = None,
) -> dict:
    if selected_types is None:
        selected_types = normalize_cloud_types(cloud_type or [SEARCH_DEFAULT_CLOUD_TYPE])
    return await unified_search_internal(
        keyword=keyword,
        selected_types=selected_types,
        force_refresh=force_refresh,
        year=year,
        media_type=tmdb_type,
        tmdb_id=tmdb_id,
        season=season,
        episode=episode,
        sort=sort,
        realtime_search_fn=lambda search_keyword: search_telegram_realtime_internal(
            search_keyword,
            channels=channels,
            selected_types=selected_types,
        ),
    )
