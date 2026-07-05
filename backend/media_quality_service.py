# -*- coding: utf-8 -*-
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_quality_from_resolution(resolution: str | None) -> Optional[str]:
    if not resolution:
        return None

    res = resolution.lower()
    if "2160" in res or "4k" in res:
        return "4K"
    if "1080" in res:
        return "1080p"
    if "720" in res:
        return "720p"
    if "480" in res:
        return "480p"
    return None


def match_quality_filter(title: str, quality_filter: Optional[str]) -> bool:
    if not quality_filter:
        return True

    try:
        pattern = re.compile(quality_filter, re.IGNORECASE)
        return bool(pattern.search(title))
    except re.error as e:
        logger.error(f"质量过滤正则表达式错误: {quality_filter}, {e}")
        return True
