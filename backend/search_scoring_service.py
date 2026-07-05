# -*- coding: utf-8 -*-
import re

from utils import classify_resource_url, normalize_text


QUALITY_PATTERNS = {
    "4K": r"\b(?:4K|2160P?)\b",
    "1080p": r"\b1080P?\b",
    "720p": r"\b720P?\b",
    "REMUX": r"\bREMUX\b",
    "WEB-DL": r"\bWEB[-_. ]?DL\b",
    "BluRay": r"\bBluRay\b",
    "HDR": r"\b(?:HDR10\+?|HDR|DoVi|Dolby\s*Vision)\b",
}


RISK_PATTERNS = (
    r"广告",
    r"博彩",
    r"娱乐城",
    r"搜索引擎",
    r"频道互推",
)


def extract_quality_tags(text: str) -> list[str]:
    tags = []
    for label, pattern in QUALITY_PATTERNS.items():
        if re.search(pattern, text or "", re.IGNORECASE):
            tags.append(label)
    return tags


def _coerce_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _quality_rank(tags: list[str]) -> int:
    ranks = {
        "4K": 70,
        "REMUX": 60,
        "BluRay": 50,
        "WEB-DL": 40,
        "1080p": 30,
        "HDR": 20,
        "720p": 10,
    }
    return max((ranks.get(tag, 0) for tag in tags), default=0)


def _contains_episode_target(text: str, season: int | None, episode: int | None) -> bool:
    if not episode:
        return False
    if season and re.search(rf"\bS0?{season}\s*E0?{episode}\b", text or "", re.IGNORECASE):
        return True
    if season and re.search(rf"第\s*{season}\s*季.{{0,12}}?第\s*{episode}\s*[集话話]", text or "", re.IGNORECASE):
        return True
    return bool(re.search(rf"(?:\bEP?0?{episode}\b|第\s*{episode}\s*[集话話])", text or "", re.IGNORECASE))


def score_search_result(
    item: dict,
    keyword: str,
    year: int | None,
    media_type: str | None,
    tmdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
) -> dict:
    text = "\n".join([
        item.get("title") or "",
        item.get("description") or "",
        item.get("raw_text") or "",
    ])
    title_norm = normalize_text(item.get("title") or "")
    keyword_norm = normalize_text(keyword)
    score = 0.0
    reasons = []

    if keyword_norm and title_norm:
        if keyword_norm == title_norm:
            score += 42
            reasons.append("标题完全匹配")
        elif keyword_norm in title_norm:
            score += 34
            reasons.append("标题包含关键词")
        else:
            tokens = [normalize_text(part) for part in re.split(r"[\s:：·\-_–—]+", keyword) if normalize_text(part)]
            meaningful = [token for token in tokens if len(token) >= 2]
            if meaningful and all(token in title_norm for token in meaningful):
                score += 24
                reasons.append("标题分词匹配")

    if year and str(year) in text:
        score += 12
        reasons.append("年份匹配")

    requested_tmdb_id = _coerce_int(tmdb_id)
    item_tmdb_id = _coerce_int(item.get("tmdb_id") or item.get("tmdbId"))
    if requested_tmdb_id and item_tmdb_id:
        if requested_tmdb_id == item_tmdb_id:
            score += 28
            reasons.append("TMDB匹配")
        else:
            score -= 35
            reasons.append("TMDB不匹配")

    if media_type == "tv" and re.search(r"S\d{1,2}E\d{1,4}|第\s*\d+\s*集|EP?\d{1,4}", text, re.IGNORECASE):
        score += 8
        reasons.append("包含剧集信息")

    if media_type == "tv" and _contains_episode_target(text, season, episode):
        score += 18
        reasons.append("目标集数匹配")

    link_type = (item.get("link_type") or classify_resource_url(item.get("resource_url") or item.get("url") or "")).lower()
    if link_type == "115":
        score += 12
        reasons.append("115链接")

    source = item.get("source")
    if source == "pansou":
        score += 8
        reasons.append("PanSou来源")
    elif source == "public_realtime":
        score += 6
        reasons.append("TG实时来源")

    quality_tags = extract_quality_tags(text)
    if quality_tags:
        score += min(12, len(quality_tags) * 3)
        reasons.append("质量标签: " + "、".join(quality_tags[:4]))

    if item.get("library_status") in {"in_library", "partial_library"}:
        score -= 20
        reasons.append("媒体库已有")
    if item.get("subscription_state", {}).get("status") == "completed":
        score -= 15
        reasons.append("订阅已完成")

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in RISK_PATTERNS):
        score -= 18
        reasons.append("疑似推广内容")

    if item.get("confidence"):
        score += float(item.get("confidence") or 0) * 10

    scored = dict(item)
    scored["score"] = round(max(score, 0), 2)
    scored["score_reason"] = "、".join(reasons) or "基础排序"
    scored["quality_tags"] = quality_tags
    return scored


def score_and_sort_results(
    items: list[dict],
    keyword: str,
    year: int | None,
    media_type: str | None,
    *,
    tmdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    sort: str | None = None,
) -> list[dict]:
    scored = [
        score_search_result(item, keyword, year, media_type, tmdb_id, season, episode)
        for item in items
    ]
    sort_mode = (sort or "score").lower()
    if sort_mode == "latest":
        def key_fn(item):
            return item.get("publish_date") or "", item.get("score") or 0
    elif sort_mode == "quality":
        def key_fn(item):
            return _quality_rank(item.get("quality_tags") or []), item.get("score") or 0, item.get("publish_date") or ""
    elif sort_mode in {"relevance", "relevant", "confidence"}:
        def key_fn(item):
            return item.get("confidence") or 0, item.get("score") or 0, item.get("publish_date") or ""
    else:
        def key_fn(item):
            return item.get("score") or 0, item.get("confidence") or 0, item.get("publish_date") or ""
    scored.sort(key=key_fn, reverse=True)
    return scored
