# -*- coding: utf-8 -*-
import json
import time

from cache_repository import (
    delete_expired_cache_rows,
    get_cache_payload_json,
    list_cache_stat_rows,
    set_cache_payload_json,
)
from config import DB_PATH


VALID_CACHE_TABLES = {"search_cache", "poster_cache", "douban_cache"}


def _selected_cache_tables(table: str | None = None) -> list[str]:
    if table:
        return [table] if table in VALID_CACHE_TABLES else []
    return sorted(VALID_CACHE_TABLES)


async def get_json_cache(table: str, cache_key: str) -> dict | None:
    if table not in VALID_CACHE_TABLES:
        return None
    now = time.time()
    payload_json = await get_cache_payload_json(table, cache_key, now, db_path=DB_PATH)
    if not payload_json:
        return None
    try:
        payload = json.loads(payload_json)
        payload["cached"] = True
        return payload
    except Exception:
        return None


async def set_json_cache(table: str, cache_key: str, payload: dict, ttl_seconds: int) -> None:
    if table not in VALID_CACHE_TABLES:
        return
    payload_json = json.dumps(payload, ensure_ascii=False)
    expires_at = time.time() + ttl_seconds
    await set_cache_payload_json(
        table,
        cache_key,
        payload_json,
        expires_at,
        keyword=payload.get("filters", {}).get("keyword", ""),
        db_path=DB_PATH,
    )


async def get_cache_stats(table: str | None = None) -> dict:
    now = time.time()
    items = await list_cache_stat_rows(_selected_cache_tables(table), now, db_path=DB_PATH)
    return {
        "items": items,
        "total": sum(item["total"] for item in items),
        "active": sum(item["active"] for item in items),
        "expired": sum(item["expired"] for item in items),
    }


async def cleanup_expired_caches(table: str | None = None) -> dict:
    now = time.time()
    deleted = await delete_expired_cache_rows(_selected_cache_tables(table), now, db_path=DB_PATH)
    return {
        "items": deleted,
        "deleted": sum(item["deleted"] for item in deleted),
    }
