# -*- coding: utf-8 -*-
"""
Startup data normalization and seed helpers.
"""
import aiosqlite

from config import PUBLIC_SEARCH_CHANNELS
from db_migration_service import ensure_columns
from structured_logging import log_event
from utils import normalize_channel_url


async def prepare_startup_data_for_connection(conn: aiosqlite.Connection) -> None:
    await normalize_channels(conn)
    await ensure_columns(conn, "messages", {
        "resource_url": "TEXT",
        "image_url": "TEXT",
        "tmdb_id": "INTEGER",
        "tmdb_type": "TEXT",
        "year": "INTEGER",
    })
    await prefill_public_channels(conn)


async def normalize_channels(conn: aiosqlite.Connection) -> None:
    try:
        log_event("db_seed.channels.normalize_started")
        async with conn.execute("SELECT id, url FROM channels") as cursor:
            all_channels = await cursor.fetchall()

        unique_channels = {}
        ids_to_delete = []
        updates = []
        for channel_id, channel_url in all_channels:
            normalized_url = normalize_channel_url(channel_url)
            if normalized_url in unique_channels:
                ids_to_delete.append(channel_id)
            else:
                unique_channels[normalized_url] = channel_id
                if normalized_url != channel_url:
                    updates.append((normalized_url, channel_id))

        if ids_to_delete:
            log_event("db_seed.channels.duplicates_found", count=len(ids_to_delete))
            placeholders = ",".join("?" for _ in ids_to_delete)
            await conn.execute(f"DELETE FROM channels WHERE id IN ({placeholders})", tuple(ids_to_delete))

        for normalized_url, channel_id in updates:
            await conn.execute("UPDATE channels SET url = ? WHERE id = ?", (normalized_url, channel_id))

        await conn.commit()
        log_event("db_seed.channels.normalize_completed", updated_count=len(updates), deleted_count=len(ids_to_delete))
    except Exception as exc:
        log_event("db_seed.channels.normalize_failed", "warning", error_type=type(exc).__name__)
        await conn.rollback()


async def prefill_public_channels(conn: aiosqlite.Connection) -> None:
    for channel_url in PUBLIC_SEARCH_CHANNELS:
        normalized_channel = normalize_channel_url(channel_url)
        async with conn.execute("SELECT id FROM channels WHERE url = ?", (normalized_channel,)) as cursor:
            if await cursor.fetchone() is None:
                await conn.execute("INSERT INTO channels (url) VALUES (?)", (normalized_channel,))
