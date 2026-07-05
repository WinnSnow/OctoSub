# -*- coding: utf-8 -*-
import json
import time
from typing import Awaitable, Callable
import asyncio
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import HTTPException

from cache_service import get_json_cache, set_json_cache
from config import SEARCH_CACHE_TTL_SECONDS, SEARCH_DEFAULT_CLOUD_TYPE
from pansou_service import fetch_pansou_search
from search_match_service import estimate_search_confidence, is_search_result_relevant
from search_scoring_service import score_and_sort_results
from structured_logging import log_event
from subscription_state_service import annotate_items_with_subscription_state, strip_live_state_from_results
from title_utils import extract_result_display_title, has_meaningful_title_text
from transfer_link_service import extract_115_share_code, extract_115_share_password
from utils import classify_resource_url

RealtimeSearchFn = Callable[[str], Awaitable[list[dict]]]


async def enrich_results_with_states(items: list[dict]) -> list[dict]:
    if not items:
        return items
    items = await annotate_items_with_subscription_state(items)
    return items


def _normalized_link_key(link: str) -> str:
    clean = (link or "").strip()
    if not clean:
        return ""
    link_type = classify_resource_url(clean)
    if link_type == "115":
        share_code = extract_115_share_code(clean)
        password = extract_115_share_password(clean) or ""
        if share_code:
            return f"115:{share_code}:{password}"

    parsed = urlparse(clean)
    if not parsed.scheme or not parsed.netloc:
        return clean
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        "",
        query,
        "",
    ))


def _result_dedupe_key(item: dict) -> str:
    link = item.get("resource_url") or item.get("url")
    if link:
        return f"link:{_normalized_link_key(link)}"
    item_id = item.get("id")
    if item_id:
        return f"id:{item.get('source') or item.get('channel_name') or ''}:{item_id}"
    return json.dumps(
        {
            "title": item.get("title"),
            "channel": item.get("channel_name"),
            "date": item.get("publish_date"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _merge_unique_results(*groups: list[dict]) -> list[dict]:
    seen = set()
    merged = []
    for group in groups:
        for item in group:
            key = _result_dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _normalize_realtime_results(
    tg_results: list[dict],
    clean_keyword: str,
    selected_types: set[str],
    year: int | None,
    media_type: str | None,
) -> list[dict]:
    normalized = []
    for item in tg_results:
        display_title = extract_result_display_title(item, clean_keyword)
        raw_title = item.get("title") or ""
        title_for_match = raw_title if has_meaningful_title_text(raw_title) else display_title
        if not is_search_result_relevant(title_for_match, clean_keyword):
            continue
        confidence_text = title_for_match
        links = [link for link in item.get("links", []) if (link.get("type") or "").lower() in selected_types]
        if not links:
            continue
        primary = links[0]
        confidence, reason = estimate_search_confidence(confidence_text, clean_keyword, year, media_type)
        normalized_item = dict(item)
        normalized_item.update({
            "title": display_title,
            "source": "public_realtime",
            "source_label": item.get("channel_name") or "TG公开频道",
            "resource_url": primary.get("url"),
            "url": primary.get("url"),
            "link_type": primary.get("type"),
            "link_types": sorted({link.get("type") for link in links if link.get("type")}),
            "links": links,
            "confidence": confidence,
            "match_reason": reason,
        })
        normalized.append(normalized_item)
    return normalized


async def unified_search_internal(
    keyword: str,
    selected_types: set[str] | None = None,
    force_refresh: bool = False,
    year: int | None = None,
    media_type: str | None = None,
    tmdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    sort: str | None = None,
    realtime_search_fn: RealtimeSearchFn | None = None,
) -> dict:
    clean_keyword = keyword.strip()
    if not clean_keyword:
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")
    selected_types = selected_types or {SEARCH_DEFAULT_CLOUD_TYPE.lower()}
    cache_key = json.dumps({
        "keyword": clean_keyword,
        "types": sorted(selected_types),
        "year": year,
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "season": season,
        "episode": episode,
        "sort": sort or "score",
    }, ensure_ascii=False, sort_keys=True)
    if not force_refresh:
        cached = await get_json_cache("search_cache", cache_key)
        if cached:
            cached["results"] = await enrich_results_with_states(cached.get("results", []))
            log_event(
                "search.cache_hit",
                keyword=clean_keyword,
                total=len(cached.get("results", [])),
                cloud_types=sorted(selected_types),
                year=year,
                media_type=media_type,
            )
            return cached

    started = time.perf_counter()
    failed_sources = []
    results = []
    raw_total = 0
    primary_source = "pansou"
    pansou_task = asyncio.create_task(fetch_pansou_search(clean_keyword, selected_types, year, media_type))
    realtime_task = asyncio.create_task(realtime_search_fn(clean_keyword)) if realtime_search_fn else None

    pansou_results = []
    realtime_results = []
    settled = await asyncio.gather(
        pansou_task,
        realtime_task if realtime_task else asyncio.sleep(0, result=None),
        return_exceptions=True,
    )
    pansou_payload, realtime_payload = settled
    if isinstance(pansou_payload, Exception):
        failed_sources.append({"source": "pansou", "error": str(pansou_payload)})
    else:
        pansou_results = pansou_payload["results"]
        raw_total = pansou_payload["raw_total"]

    if realtime_task:
        if isinstance(realtime_payload, Exception):
            failed_sources.append({"source": "public_realtime", "error": str(realtime_payload)})
        else:
            realtime_results = _normalize_realtime_results(
                realtime_payload,
                clean_keyword,
                selected_types,
                year,
                media_type,
            )

    results = score_and_sort_results(
        _merge_unique_results(pansou_results, realtime_results),
        clean_keyword,
        year,
        media_type,
        tmdb_id=tmdb_id,
        season=season,
        episode=episode,
        sort=sort,
    )
    if pansou_results and realtime_results:
        primary_source = "combined"
    elif realtime_results:
        primary_source = "public_realtime"

    payload = {
        "source": primary_source,
        "results": results,
        "total": len(results),
        "raw_total": raw_total,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "failed_sources": failed_sources,
        "filters": {
            "keyword": clean_keyword,
            "cloud_types": sorted(selected_types),
            "year": year,
            "media_type": media_type,
            "tmdb_id": tmdb_id,
            "season": season,
            "episode": episode,
            "sort": sort or "score",
        },
        "cached": False,
    }
    log_event(
        "search.completed",
        keyword=clean_keyword,
        source=primary_source,
        total=payload["total"],
        raw_total=raw_total,
        elapsed_ms=payload["elapsed_ms"],
        failed_sources=len(failed_sources),
        cloud_types=sorted(selected_types),
        year=year,
        media_type=media_type,
        tmdb_id=tmdb_id,
        season=season,
        episode=episode,
        sort=sort or "score",
    )
    await set_json_cache("search_cache", cache_key, strip_live_state_from_results(payload), SEARCH_CACHE_TTL_SECONDS)
    payload["results"] = await enrich_results_with_states(payload["results"])
    return payload
