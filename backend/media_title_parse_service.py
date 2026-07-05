# -*- coding: utf-8 -*-
"""
Media title parsing helpers backed by PTN.
"""
import logging
import re
from typing import Any, Dict, Optional, Tuple

import PTN

from media_identity_service import coerce_media_number, generate_fingerprint
from media_quality_service import normalize_quality_from_resolution

logger = logging.getLogger(__name__)


def parse_media_title(title: str) -> Dict[str, Any]:
    try:
        parsed = PTN.parse(title)
        result = {
            "title": parsed.get("title", ""),
            "season": coerce_media_number(parsed.get("season")),
            "episode": coerce_media_number(parsed.get("episode")),
            "resolution": parsed.get("resolution"),
            "quality": parsed.get("quality"),
            "year": coerce_media_number(parsed.get("year")),
            "codec": parsed.get("codec"),
            "audio": parsed.get("audio"),
            "group": parsed.get("group"),
            "type": "episode" if parsed.get("season") or parsed.get("episode") else "movie",
        }

        normalized_quality = normalize_quality_from_resolution(result["resolution"])
        if normalized_quality:
            result["quality"] = normalized_quality

        logger.debug(f"解析标题: {title} -> {result}")
        return result
    except Exception as e:
        logger.error(f"解析标题失败 '{title}': {e}")
        return {
            "title": title,
            "season": None,
            "episode": None,
            "resolution": None,
            "quality": None,
            "year": None,
            "codec": None,
            "audio": None,
            "group": None,
            "type": "unknown",
        }


def extract_season_episode(title: str) -> Tuple[Optional[int], Optional[int]]:
    parsed = parse_media_title(title)
    return parsed.get("season"), parsed.get("episode")


def extract_quality(title: str) -> Optional[str]:
    parsed = parse_media_title(title)
    return parsed.get("quality") or parsed.get("resolution")


def extract_year_from_title(title: str) -> Optional[int]:
    parsed = parse_media_title(title)
    year = parsed.get("year")
    if year:
        return year

    match = re.search(r"\b(19\d{2}|20\d{2})\b", title)
    if match:
        return int(match.group(1))
    return None


def is_episode(title: str) -> bool:
    parsed = parse_media_title(title)
    return parsed.get("type") == "episode"


def is_movie(title: str) -> bool:
    parsed = parse_media_title(title)
    return parsed.get("type") == "movie"


def parse_and_generate_fingerprint(title: str) -> Tuple[Dict[str, Any], str]:
    parsed = parse_media_title(title)
    fingerprint = generate_fingerprint(parsed)
    return parsed, fingerprint
