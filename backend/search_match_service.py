# -*- coding: utf-8 -*-
import re

from utils import normalize_text


def estimate_search_confidence(
    result_title: str,
    keyword: str,
    year: int | None = None,
    media_type: str | None = None,
) -> tuple[float, str]:
    title_norm = normalize_text(result_title)
    keyword_norm = normalize_text(keyword)
    score = 0.55
    reasons = []
    if keyword_norm and keyword_norm in title_norm:
        score += 0.25
        reasons.append("标题包含关键词")
    else:
        partial_tokens = [
            normalize_text(part)
            for part in re.split(r"\s+", keyword.lower())
            if part and not part.isdigit() and normalize_text(part)
        ]
        if title_norm and keyword_norm and any(part in title_norm for part in partial_tokens):
            score += 0.12
            reasons.append("标题部分匹配")
    if year and str(year) in (result_title or ""):
        score += 0.1
        reasons.append("年份匹配")
    if media_type == "tv" and re.search(r"S\d{1,2}|第\s*\d+\s*季|EP?\d{1,3}", result_title or "", re.IGNORECASE):
        score += 0.05
        reasons.append("剧集信息匹配")
    return min(round(score, 2), 0.98), "、".join(reasons) or "基础匹配"


def is_search_result_relevant(result_title: str, keyword: str) -> bool:
    title_norm = normalize_text(result_title)
    keyword_norm = normalize_text(keyword)
    if not title_norm or not keyword_norm:
        return False
    if keyword_norm in title_norm:
        return True

    tokens = [
        normalize_text(token)
        for token in re.split(r"[\s\-_:：·]+", keyword)
        if normalize_text(token)
    ]
    meaningful_tokens = [token for token in tokens if len(token) >= 2]
    return bool(meaningful_tokens) and all(token in title_norm for token in meaningful_tokens)
