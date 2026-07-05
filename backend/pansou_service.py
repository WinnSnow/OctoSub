# -*- coding: utf-8 -*-
import aiohttp

from config import PANSOU_BASE_URL, PANSOU_ENABLED, PANSOU_TIMEOUT_SECONDS
from search_match_service import estimate_search_confidence, is_search_result_relevant
from title_utils import build_library_check_title, extract_display_title
from utils import classify_resource_url, link_with_password, stable_hash


def normalize_pansou_results(
    raw_payload: dict,
    keyword: str,
    selected_types: set[str],
    year: int | None = None,
    media_type: str | None = None,
) -> list[dict]:
    data = raw_payload.get("data") if isinstance(raw_payload, dict) else {}
    merged = (data or {}).get("merged_by_type") or {}
    results = []
    seen_links = set()
    for type_key, items in merged.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            if not url:
                continue
            link_type = (type_key or classify_resource_url(url) or "others").lower()
            if link_type not in selected_types:
                continue
            password = (item.get("password") or "").strip() or None
            final_url = link_with_password(url, password)
            if final_url in seen_links:
                continue
            seen_links.add(final_url)
            title = extract_display_title(item.get("note"), keyword)
            if not is_search_result_relevant(title, keyword):
                continue
            confidence, reason = estimate_search_confidence(title, keyword, year, media_type)
            result_id = f"pansou:{link_type}:{stable_hash(final_url + title)}"
            images = item.get("images") if isinstance(item.get("images"), list) else []
            results.append({
                "id": result_id,
                "title": title,
                "library_check_title": build_library_check_title(keyword),
                "tmdb_type": media_type if media_type in {"movie", "tv"} else None,
                "year": year,
                "channel_name": item.get("source") or "PanSou",
                "publish_date": item.get("datetime"),
                "description": item.get("note") or "",
                "raw_text": item.get("note") or "",
                "image_url": images[0] if images else None,
                "poster_url": images[0] if images else None,
                "message_link": None,
                "resource_url": final_url,
                "url": final_url,
                "password": password,
                "link_type": link_type,
                "link_types": [link_type],
                "links": [{"url": final_url, "type": link_type, "password": password}],
                "access_code": password,
                "source": "pansou",
                "source_label": item.get("source") or "PanSou",
                "confidence": confidence,
                "match_reason": reason,
            })
    results.sort(key=lambda item: (item.get("confidence") or 0, item.get("publish_date") or ""), reverse=True)
    return results


async def fetch_pansou_search(
    keyword: str,
    selected_types: set[str],
    year: int | None = None,
    media_type: str | None = None,
) -> dict:
    if not PANSOU_ENABLED:
        raise RuntimeError("PanSou 未启用")
    timeout = aiohttp.ClientTimeout(total=PANSOU_TIMEOUT_SECONDS)
    params = {"kw": keyword, "src": "all"}
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{PANSOU_BASE_URL}/api/search", params=params) as response:
            if response.status >= 400:
                raise RuntimeError(f"PanSou HTTP {response.status}")
            raw_payload = await response.json(content_type=None)
    return {
        "results": normalize_pansou_results(raw_payload, keyword, selected_types, year, media_type),
        "raw_total": ((raw_payload.get("data") or {}).get("total") if isinstance(raw_payload, dict) else 0) or 0,
    }
