# -*- coding: utf-8 -*-
import re
from typing import Any, Optional


def coerce_media_number(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            coerced = coerce_media_number(item)
            if coerced is not None:
                return coerced
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def generate_fingerprint(parsed: dict[str, Any]) -> str:
    """
    Generate a business fingerprint for media dedupe.
    """
    title = parsed.get("title", "Unknown").strip()

    if parsed.get("type") == "episode":
        season = coerce_media_number(parsed.get("season"))
        episode = coerce_media_number(parsed.get("episode"))

        if season is not None and episode is not None:
            return f"{title}_S{season:02d}_E{episode:02d}"
        if episode is not None:
            return f"{title}_S01_E{episode:02d}"
        return f"{title}_Episode"

    if parsed.get("type") == "movie":
        year = coerce_media_number(parsed.get("year"))
        if year:
            return f"{title}_Movie_{year}"
        return f"{title}_Movie"

    return f"{title}_Unknown"


def normalize_title(title: str) -> str:
    normalized = re.sub(r"[^\w\s]", "", title)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.lower().strip()


def is_similar_title(title1: str, title2: str, threshold: float = 0.8) -> bool:
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if norm1 in norm2 or norm2 in norm1:
        return True

    words1 = set(norm1.split())
    words2 = set(norm2.split())
    if not words1 or not words2:
        return False

    similarity = len(words1 & words2) / len(words1 | words2)
    return similarity >= threshold
