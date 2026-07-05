# -*- coding: utf-8 -*-
from fastapi import HTTPException

from cache_service import get_json_cache, set_json_cache
from config import DB_PATH
from db import connect_db
from poster_fetch_service import PosterMatchResult as PosterMatchResult
from poster_fetch_service import fetch_poster_for_identity
from poster_identity_service import build_media_identity as build_media_identity
from poster_identity_service import detect_media_type as detect_media_type
from poster_match_batch_service import match_posters_for_message_batch
from task_service import cancel_task, is_cancel_requested, update_task


TMDB_IMAGE_PREFIX = "https://image.tmdb.org/"

__all__ = [
    "PosterMatchResult",
    "build_media_identity",
    "detect_media_type",
    "match_posters_for_messages",
    "match_single_message_poster",
]


async def match_posters_for_messages(
    message_ids: list[int] | None = None,
    proxy_config: dict | None = None,
    concurrency: int = 5,
    ignore_cached_misses: bool = False,
    task_id: str | None = None,
) -> dict:
    return await match_posters_for_message_batch(
        db_path=DB_PATH,
        message_ids=message_ids,
        proxy_config=proxy_config,
        concurrency=concurrency,
        ignore_cached_misses=ignore_cached_misses,
        get_json_cache_fn=get_json_cache,
        set_json_cache_fn=set_json_cache,
        fetch_poster_for_identity_fn=fetch_poster_for_identity,
        task_id=task_id,
        update_task_fn=update_task,
        is_cancel_requested_fn=is_cancel_requested,
        cancel_task_fn=cancel_task,
    )


async def match_single_message_poster(message_id: int, proxy_config: dict | None = None) -> dict:
    async with connect_db(DB_PATH, timeout=30.0) as conn:
        async with conn.execute(
            "SELECT id, title, raw_text, image_url FROM messages WHERE id = ?",
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row or not row[1]:
        raise HTTPException(status_code=404, detail="未找到消息或消息无标题")

    stats = await match_posters_for_messages(
        [message_id],
        proxy_config=proxy_config,
        ignore_cached_misses=True,
    )
    async with connect_db(DB_PATH, timeout=30.0) as conn:
        async with conn.execute("SELECT image_url FROM messages WHERE id = ?", (message_id,)) as cursor:
            updated_row = await cursor.fetchone()

    poster_url = updated_row[0] if updated_row else None
    if poster_url and poster_url.startswith(TMDB_IMAGE_PREFIX):
        source = "unknown"
        if stats.get("database_key_cache_hits"):
            source = "database_key_cache"
        elif stats.get("poster_cache_hits"):
            source = "poster_cache"
        elif stats.get("tmdb_requests"):
            source = "tmdb_api"
        return {"status": "success", "image_url": poster_url, "source": source}
    return {"status": "failed", "message": "未找到海报"}
