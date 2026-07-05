# -*- coding: utf-8 -*-

import aiosqlite

from config import DB_PATH
from db import connect_db


async def messages_fts_available(conn: aiosqlite.Connection) -> bool:
    async with conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'messages_fts'"
    ) as cursor:
        return await cursor.fetchone() is not None


async def count_message_rows(
    *,
    where_sql: str,
    params: list,
    conn: aiosqlite.Connection,
) -> int:
    async with conn.execute(f"SELECT COUNT(*) FROM messages{where_sql}", tuple(params)) as cursor:
        row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def list_message_rows(
    *,
    where_sql: str,
    params: list,
    conn: aiosqlite.Connection,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    limit_sql = " LIMIT ? OFFSET ?" if limit is not None and offset is not None else ""
    query_params = [*params, limit, offset] if limit is not None and offset is not None else list(params)
    async with conn.execute(
        f"SELECT * FROM messages{where_sql} ORDER BY publish_date DESC, id DESC{limit_sql}",
        tuple(query_params),
    ) as cursor:
        return [dict(row) for row in await cursor.fetchall()]


async def list_source_count_rows(
    *,
    where_sql: str,
    params: list,
    conn: aiosqlite.Connection,
) -> list[dict]:
    async with conn.execute(
        f"""
        SELECT channel_name, COUNT(*) AS count
        FROM messages
        {where_sql}
        GROUP BY channel_name
        ORDER BY count DESC, channel_name ASC
        """,
        tuple(params),
    ) as cursor:
        return [dict(row) for row in await cursor.fetchall()]


async def list_links_by_message_ids(
    message_ids: list[int],
    *,
    conn: aiosqlite.Connection,
) -> dict[int, list[dict]]:
    links_by_message_id = {message_id: [] for message_id in message_ids}
    if not message_ids:
        return links_by_message_id
    placeholders = ",".join("?" for _ in message_ids)
    async with conn.execute(
        f"SELECT * FROM links WHERE message_id IN ({placeholders})",
        tuple(message_ids),
    ) as links_cursor:
        for link_row in await links_cursor.fetchall():
            links_by_message_id[link_row["message_id"]].append(dict(link_row))
    return links_by_message_id


def open_message_connection(db_path: str = DB_PATH):
    return connect_db(db_path, row_factory=aiosqlite.Row)
