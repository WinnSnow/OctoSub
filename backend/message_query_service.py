# -*- coding: utf-8 -*-
import re
import time

import aiosqlite

from config import DB_PATH
from message_query_repository import (
    count_message_rows,
    list_links_by_message_ids,
    list_message_rows,
    list_source_count_rows,
    messages_fts_available,
    open_message_connection,
)


SOURCES_CACHE_TTL_SECONDS = 10
_SOURCES_CACHE: dict[tuple, tuple[float, list[dict]]] = {}


def _build_fts_match_query(search: str | None) -> str | None:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_]+", search or "")
        if len(token) >= 2
    ]
    if not tokens:
        return None
    return " ".join(f"title:{token}*" for token in tokens[:8])


async def _messages_fts_available(conn: aiosqlite.Connection) -> bool:
    return await messages_fts_available(conn)


def _sources_cache_key(db_path: str, where_sql: str, params: list) -> tuple:
    return (db_path, where_sql, tuple(params))


async def _build_message_base_filter(conn: aiosqlite.Connection, search: str | None) -> tuple[list[str], list]:
    clauses = ["""
        (
            (resource_url IS NOT NULL AND resource_url != '')
            OR EXISTS (
                SELECT 1 FROM links resource_links
                WHERE resource_links.message_id = messages.id
            )
        )
    """]
    params = []

    if search:
        fts_query = _build_fts_match_query(search)
        if fts_query and await _messages_fts_available(conn):
            clauses.append("messages.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)")
            params.append(fts_query)
        else:
            clauses.append("title LIKE ?")
            search_term = f"%{search}%"
            params.append(search_term)

    return clauses, params


def _where_sql(clauses: list[str]) -> str:
    if not clauses:
        return ""
    return " WHERE " + " AND ".join(clauses)


def _selected_channels(channel_name: str | None, channel_names: list[str] | None) -> list[str]:
    if not isinstance(channel_names, (list, tuple)):
        channel_names = []
    selected = [item for item in channel_names if item]
    if channel_name and channel_name not in selected:
        selected.append(channel_name)
    return selected


def _apply_channel_filter(
    clauses: list[str],
    params: list,
    selected_channels: list[str],
) -> tuple[list[str], list]:
    next_clauses = list(clauses)
    next_params = list(params)
    if selected_channels:
        placeholders = ",".join("?" for _ in selected_channels)
        next_clauses.append(f"channel_name IN ({placeholders})")
        next_params.extend(selected_channels)
    return next_clauses, next_params


async def _get_cached_sources(
    conn: aiosqlite.Connection,
    db_path: str,
    where_sql: str,
    params: list,
) -> list[dict]:
    key = _sources_cache_key(db_path, where_sql, params)
    now = time.time()
    cached = _SOURCES_CACHE.get(key)
    if cached and now - cached[0] <= SOURCES_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    source_rows = await list_source_count_rows(where_sql=where_sql, params=params, conn=conn)
    sources = [
        {"channel_name": row["channel_name"], "count": row["count"]}
        for row in source_rows
        if row["channel_name"]
    ]
    _SOURCES_CACHE[key] = (now, sources)
    return [dict(item) for item in sources]


def clear_sources_cache() -> None:
    _SOURCES_CACHE.clear()


async def get_local_messages_payload(
    *,
    page: int = 1,
    limit: int = 25,
    channel_name: str | None = None,
    channel_names: list[str] | None = None,
    search: str | None = None,
    db_path: str = DB_PATH,
) -> dict:
    page = max(1, min(page, 100000))
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit
    async with open_message_connection(db_path) as conn:
        base_where_clauses, base_params = await _build_message_base_filter(conn, search)
        base_where_sql = _where_sql(base_where_clauses)
        sources = await _get_cached_sources(conn, db_path, base_where_sql, base_params)
        where_clauses, params = _apply_channel_filter(
            base_where_clauses,
            base_params,
            _selected_channels(channel_name, channel_names),
        )
        where_sql = _where_sql(where_clauses)

        total = await count_message_rows(where_sql=where_sql, params=params, conn=conn)
        messages_rows = await list_message_rows(
            where_sql=where_sql,
            params=params,
            limit=limit,
            offset=offset,
            conn=conn,
        )

        messages = []
        message_ids = [row["id"] for row in messages_rows]
        links_by_message_id = await list_links_by_message_ids(message_ids, conn=conn)
        for msg_row in messages_rows:
            message_dict = dict(msg_row)
            message_dict["links"] = links_by_message_id.get(message_dict["id"], [])
            message_dict["source"] = "local_library"
            message_dict["source_label"] = message_dict.get("channel_name") or "本地库"
            messages.append(message_dict)

    return {"messages": messages, "total": total, "page": page, "limit": limit, "sources": sources}
