# -*- coding: utf-8 -*-
import json


def dedupe_urls(urls: list[str | None]) -> list[str]:
    seen = set()
    deduped = []
    for url in urls:
        clean = (url or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def row_get(row, key: str, default=None):
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def decode_quality_tags(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        tags = json.loads(value)
        return tags if isinstance(tags, list) else []
    except Exception:
        return []
