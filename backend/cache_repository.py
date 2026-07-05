# -*- coding: utf-8 -*-
import sqlite3

from config import DB_PATH
from db import connect_db


async def get_cache_payload_json(table: str, cache_key: str, now: float, *, db_path: str = DB_PATH) -> str | None:
    try:
        async with connect_db(db_path) as conn:
            async with conn.execute(
                f"SELECT payload_json FROM {table} WHERE cache_key = ? AND expires_at > ?",
                (cache_key, now),
            ) as cursor:
                row = await cursor.fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


async def table_columns(conn, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cursor:
        return {row[1] for row in await cursor.fetchall()}


async def set_cache_payload_json(
    table: str,
    cache_key: str,
    payload_json: str,
    expires_at: float,
    *,
    keyword: str = "",
    db_path: str = DB_PATH,
) -> None:
    try:
        async with connect_db(db_path) as conn:
            if table == "search_cache":
                columns = await table_columns(conn, "search_cache")
                if {"keyword", "results"}.issubset(columns):
                    await conn.execute(
                        """
                        INSERT OR REPLACE INTO search_cache
                            (cache_key, keyword, plugins, results, payload_json, expires_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (cache_key, keyword, "", payload_json, payload_json, expires_at),
                    )
                else:
                    await conn.execute(
                        """
                        INSERT OR REPLACE INTO search_cache (cache_key, payload_json, expires_at, created_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (cache_key, payload_json, expires_at),
                    )
            else:
                await conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (cache_key, payload_json, expires_at, created_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (cache_key, payload_json, expires_at),
                )
            await conn.commit()
    except sqlite3.OperationalError:
        return


async def table_exists(conn, table: str) -> bool:
    async with conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ) as cursor:
        return await cursor.fetchone() is not None


async def list_cache_stat_rows(tables: list[str], now: float, *, db_path: str = DB_PATH) -> list[dict]:
    items = []
    async with connect_db(db_path) as conn:
        for cache_table in tables:
            if not await table_exists(conn, cache_table):
                continue
            async with conn.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN expires_at <= ? THEN 1 ELSE 0 END) AS expired,
                    MIN(created_at) AS oldest_created_at,
                    MAX(created_at) AS newest_created_at
                FROM {cache_table}
                """,
                (now, now),
            ) as cursor:
                row = await cursor.fetchone()
            items.append({
                "table": cache_table,
                "total": int(row[0] or 0),
                "active": int(row[1] or 0),
                "expired": int(row[2] or 0),
                "oldest_created_at": row[3],
                "newest_created_at": row[4],
            })
    return items


async def delete_expired_cache_rows(tables: list[str], now: float, *, db_path: str = DB_PATH) -> list[dict]:
    deleted = []
    async with connect_db(db_path) as conn:
        for cache_table in tables:
            if not await table_exists(conn, cache_table):
                continue
            cursor = await conn.execute(f"DELETE FROM {cache_table} WHERE expires_at <= ?", (now,))
            deleted.append({"table": cache_table, "deleted": cursor.rowcount})
        await conn.commit()
    return deleted
