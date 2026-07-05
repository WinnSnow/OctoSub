# -*- coding: utf-8 -*-
import json

import aiosqlite

from config import DB_PATH
from media_parser import parse_media_title
from resource_index_schema_service import ensure_resource_index_schema, resource_index_available
from resource_index_utils import dedupe_urls, row_get
from search_scoring_service import extract_quality_tags
from utils import classify_resource_url


async def rebuild_resource_index_for_message(
    message_id: int,
    *,
    conn: aiosqlite.Connection | None = None,
) -> int:
    owns_conn = conn is None
    if conn is None:
        conn = await aiosqlite.connect(DB_PATH)
    try:
        await ensure_resource_index_schema(conn)
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)) as cursor:
            message = await cursor.fetchone()
        if not message:
            await conn.execute("DELETE FROM resource_index WHERE message_id = ?", (message_id,))
            if owns_conn:
                await conn.commit()
            return 0

        async with conn.execute("SELECT url FROM links WHERE message_id = ? ORDER BY id", (message_id,)) as cursor:
            link_rows = await cursor.fetchall()
        urls = dedupe_urls([row_get(message, "resource_url"), *[row["url"] for row in link_rows]])

        await conn.execute("DELETE FROM resource_index WHERE message_id = ?", (message_id,))
        if not urls:
            if owns_conn:
                await conn.commit()
            return 0

        rows = build_resource_index_rows(message, urls)
        await conn.executemany(
            """
            INSERT OR REPLACE INTO resource_index (
                message_id, channel_name, source_message_id, title, description, raw_text,
                url, link_type, tmdb_id, tmdb_type, year, season, episode,
                quality_tags_json, publish_date, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            rows,
        )
        if owns_conn:
            await conn.commit()
        return len(rows)
    finally:
        if owns_conn:
            await conn.close()


def build_resource_index_rows(message, urls: list[str]) -> list[tuple]:
    title = row_get(message, "title", "") or ""
    description = row_get(message, "description", "") or ""
    raw_text = row_get(message, "raw_text", "") or ""
    text = "\n".join([title, description, raw_text])
    parsed = parse_media_title(title)
    quality_tags = extract_quality_tags(text)
    return [
        (
            message["id"],
            row_get(message, "channel_name"),
            row_get(message, "message_id"),
            title,
            description,
            raw_text,
            url,
            classify_resource_url(url),
            row_get(message, "tmdb_id"),
            row_get(message, "tmdb_type"),
            row_get(message, "year") or parsed.get("year"),
            parsed.get("season"),
            parsed.get("episode"),
            json.dumps(quality_tags, ensure_ascii=False),
            row_get(message, "publish_date"),
        )
        for url in urls
    ]


async def rebuild_resource_index_for_messages(message_ids: list[int]) -> int:
    if not message_ids:
        return 0
    async with aiosqlite.connect(DB_PATH) as conn:
        total = 0
        for message_id in message_ids:
            total += await rebuild_resource_index_for_message(message_id, conn=conn)
        await conn.commit()
        return total


async def rebuild_all_resource_index() -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        await ensure_resource_index_schema(conn)
        await conn.execute("DELETE FROM resource_index")
        async with conn.execute("""
            SELECT id
            FROM messages
            WHERE (resource_url IS NOT NULL AND resource_url != '')
               OR EXISTS (SELECT 1 FROM links WHERE links.message_id = messages.id)
            ORDER BY id
        """) as cursor:
            rows = await cursor.fetchall()
        total = 0
        for row in rows:
            total += await rebuild_resource_index_for_message(row[0], conn=conn)
        await conn.commit()
        return total


async def resource_index_needs_rebuild(conn: aiosqlite.Connection) -> bool:
    if not await resource_index_available(conn):
        return True
    async with conn.execute("SELECT COUNT(*) FROM resource_index") as cursor:
        indexed_count = (await cursor.fetchone())[0]
    if indexed_count:
        return False
    async with conn.execute("""
        SELECT COUNT(*)
        FROM messages
        WHERE (resource_url IS NOT NULL AND resource_url != '')
           OR EXISTS (SELECT 1 FROM links WHERE links.message_id = messages.id)
    """) as cursor:
        source_count = (await cursor.fetchone())[0]
    return source_count > 0
