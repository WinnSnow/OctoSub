# -*- coding: utf-8 -*-
"""
Pure Jellyfin matching helpers.

Keep these helpers free of HTTP/client state so title and provider-id matching
can be tested without touching the Jellyfin API client.
"""
import re
from typing import Any, Optional


def coerce_int(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            coerced = coerce_int(item)
            if coerced is not None:
                return coerced
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_title(value: Optional[str]) -> str:
    return re.sub(r"[\W_]+", "", (value or "").lower(), flags=re.UNICODE)


def title_variants(name: str) -> list[str]:
    base = re.sub(r"\s+", " ", (name or "").strip())
    if not base:
        return []

    variants = [base]
    no_year = re.sub(r"[\(（\[]?\b(?:19\d{2}|20\d{2})\b[\)）\]]?", "", base).strip()
    if no_year:
        variants.append(no_year)

    spaced = re.sub(r"[:：·\-_–—]+", " ", no_year or base).strip()
    if spaced:
        variants.append(spaced)

    for part in re.split(r"[:：·\-_–—]+", no_year or base):
        part = part.strip()
        if len(normalize_title(part)) >= 2:
            variants.append(part)

    seen = set()
    result = []
    for value in variants:
        key = normalize_title(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def score_item(item: dict[str, Any], query: str, year: Optional[int]) -> int:
    query_norm = normalize_title(query)
    candidate_names = [
        item.get("Name"),
        item.get("OriginalTitle"),
        item.get("SortName"),
    ]
    best = 0
    for candidate in candidate_names:
        candidate_norm = normalize_title(candidate)
        if not candidate_norm or not query_norm:
            continue
        if candidate_norm == query_norm:
            best = max(best, 100)
        elif query_norm in candidate_norm or candidate_norm in query_norm:
            best = max(best, 86)
        else:
            query_parts = [
                normalize_title(part)
                for part in re.split(r"[\s:：·\-_–—]+", query)
                if len(normalize_title(part)) >= 2
            ]
            if query_parts and all(part in candidate_norm for part in query_parts):
                best = max(best, 74)

    production_year = item.get("ProductionYear")
    if year and production_year:
        if int(production_year) == int(year):
            best += 8
        elif best < 90:
            best -= 6
    return best


def choose_best_item(
    items: list[dict[str, Any]],
    queries: list[str],
    year: Optional[int] = None,
    min_score: int = 50,
) -> tuple[Optional[dict[str, Any]], int]:
    if not items:
        return None, 0

    scored = []
    for item in items:
        score = max(score_item(item, query, year) for query in queries)
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    best_score, best_item = scored[0]
    if best_score >= min_score:
        return best_item, best_score
    return None, best_score


def extract_provider_tmdb_id(item: dict[str, Any]) -> Optional[int]:
    provider_ids = item.get("ProviderIds") or {}
    return coerce_int(provider_ids.get("Tmdb") or provider_ids.get("TMDb") or provider_ids.get("TMDB"))


def find_item_by_provider_tmdb_id(
    items: list[dict[str, Any]],
    tmdb_id: int,
) -> Optional[dict[str, Any]]:
    coerced_tmdb_id = coerce_int(tmdb_id)
    if not coerced_tmdb_id:
        return None

    for item in items:
        if extract_provider_tmdb_id(item) == coerced_tmdb_id:
            return item
    return None
