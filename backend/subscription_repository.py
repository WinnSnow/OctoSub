# -*- coding: utf-8 -*-
import json

import aiosqlite

from config import DB_PATH, SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE
from db import connect_db


SUBSCRIPTION_BASE_SELECT = """
SELECT id, keyword, quality_filter, media_type, created_at, updated_at,
       tmdb_id, tmdb_type, year, poster_url, enabled, auto_transfer,
       min_confidence, last_checked_at, status, completed_at,
       completion_reason, progress_current, progress_total, episode_state_json,
       target_seasons_json
"""

DOUBAN_SUBSCRIPTION_COLUMNS = ("douban_id", "douban_url", "douban_rating", "metadata_source")


async def table_has_column(conn, table_name: str, column_name: str) -> bool:
    async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
        return column_name in {row[1] for row in await cursor.fetchall()}


async def _subscription_select_sql(conn) -> str:
    douban_columns = []
    for column in DOUBAN_SUBSCRIPTION_COLUMNS:
        if await table_has_column(conn, "subscriptions", column):
            douban_columns.append(column)
        else:
            douban_columns.append(f"NULL AS {column}")
    return f"{SUBSCRIPTION_BASE_SELECT}, {', '.join(douban_columns)} FROM subscriptions"


async def _has_douban_subscription_columns(conn) -> bool:
    return all([await table_has_column(conn, "subscriptions", column) for column in DOUBAN_SUBSCRIPTION_COLUMNS])


def _target_seasons_json(target_seasons) -> str | None:
    return json.dumps(target_seasons, ensure_ascii=False, separators=(",", ":")) if target_seasons is not None else None


async def list_subscription_rows(*, db_path: str = DB_PATH) -> list:
    async with connect_db(db_path) as conn:
        select_sql = await _subscription_select_sql(conn)
        async with conn.execute(f"{select_sql} ORDER BY id DESC") as cursor:
            return await cursor.fetchall()


async def list_subscription_ids(
    *,
    subscription_id: int | None = None,
    db_path: str = DB_PATH,
) -> list[int]:
    params: list[int] = []
    where_clause = ""
    if subscription_id is not None:
        where_clause = "WHERE id = ?"
        params.append(subscription_id)
    async with connect_db(db_path) as conn:
        async with conn.execute(f"SELECT id FROM subscriptions {where_clause} ORDER BY id DESC", params) as cursor:
            rows = await cursor.fetchall()
    return [int(row[0]) for row in rows]


async def get_subscription_active_state(subscription_id: int, *, db_path: str = DB_PATH) -> bool | None:
    async with connect_db(db_path) as conn:
        async with conn.execute(
            """
            SELECT COALESCE(enabled, 1), COALESCE(status, 'active')
            FROM subscriptions
            WHERE id = ?
            """,
            (subscription_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return bool(row[0]) and row[1] == "active"


async def insert_subscription(payload, *, keyword: str, quality_filter: str | None, media_type: str, db_path: str = DB_PATH):
    target_seasons_json = _target_seasons_json(payload.target_seasons)
    async with connect_db(db_path) as conn:
        has_douban_columns = await _has_douban_subscription_columns(conn)
        douban_insert_columns = ", douban_id, douban_url, douban_rating, metadata_source" if has_douban_columns else ""
        douban_insert_placeholders = ", ?, ?, ?, ?" if has_douban_columns else ""
        douban_params = (
            [payload.douban_id, payload.douban_url, payload.douban_rating, payload.metadata_source]
            if has_douban_columns else []
        )
        await conn.execute(
            f"""
            INSERT INTO subscriptions
                (keyword, quality_filter, media_type, tmdb_id, tmdb_type, year, poster_url,
                 enabled, auto_transfer, min_confidence, status, completed_at, completion_reason,
                 progress_current, progress_total, episode_state_json, target_seasons_json{douban_insert_columns})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, 0, '{{}}', ?{douban_insert_placeholders})
            """,
            (
                keyword, quality_filter, media_type, payload.tmdb_id, payload.tmdb_type,
                payload.year, payload.poster_url, int(payload.enabled),
                int(payload.auto_transfer), payload.min_confidence or SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE,
                "active", target_seasons_json, *douban_params,
            ),
        )
        await conn.commit()
        async with conn.execute("SELECT last_insert_rowid()") as cursor:
            subscription_id = (await cursor.fetchone())[0]
        select_sql = await _subscription_select_sql(conn)
        async with conn.execute(f"{select_sql} WHERE id = ?", (subscription_id,)) as cursor:
            return await cursor.fetchone()


async def update_subscription(
    subscription_id: int,
    payload,
    *,
    keyword: str,
    quality_filter: str | None,
    media_type: str,
    db_path: str = DB_PATH,
):
    target_seasons_json = _target_seasons_json(payload.target_seasons)
    async with connect_db(db_path) as conn:
        has_douban_columns = await _has_douban_subscription_columns(conn)
        douban_update_sql = (
            "douban_id = ?, douban_url = ?, douban_rating = ?, metadata_source = ?,"
            if has_douban_columns else ""
        )
        douban_params = (
            [payload.douban_id, payload.douban_url, payload.douban_rating, payload.metadata_source]
            if has_douban_columns else []
        )
        cursor = await conn.execute(
            f"""
            UPDATE subscriptions
            SET keyword = ?, quality_filter = ?, media_type = ?,
                tmdb_id = ?, tmdb_type = ?, year = ?, poster_url = ?,
                enabled = ?, auto_transfer = ?, min_confidence = ?,
                status = 'active', completed_at = NULL, completion_reason = NULL,
                progress_current = 0, progress_total = 0, episode_state_json = '{{}}',
                target_seasons_json = ?,
                {douban_update_sql}
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (keyword, quality_filter, media_type, payload.tmdb_id, payload.tmdb_type,
             payload.year, payload.poster_url, int(payload.enabled), int(payload.auto_transfer),
             payload.min_confidence or SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE, target_seasons_json,
             *douban_params, subscription_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return None
        select_sql = await _subscription_select_sql(conn)
        async with conn.execute(f"{select_sql} WHERE id = ?", (subscription_id,)) as cursor:
            return await cursor.fetchone()


async def update_subscription_status(subscription_id: int, status: str, *, db_path: str = DB_PATH):
    enabled = status == "active"
    async with connect_db(db_path) as conn:
        cursor = await conn.execute(
            """
            UPDATE subscriptions
            SET status = ?,
                enabled = ?,
                completed_at = CASE
                    WHEN ? = 'completed' AND completed_at IS NULL THEN CURRENT_TIMESTAMP
                    WHEN ? != 'completed' THEN NULL
                    ELSE completed_at
                END,
                completion_reason = CASE
                    WHEN ? = 'completed' THEN COALESCE(completion_reason, 'manual_completed')
                    WHEN ? != 'completed' THEN NULL
                    ELSE completion_reason
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, int(enabled), status, status, status, status, subscription_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return None
        select_sql = await _subscription_select_sql(conn)
        async with conn.execute(f"{select_sql} WHERE id = ?", (subscription_id,)) as cursor:
            return await cursor.fetchone()


async def delete_subscription(subscription_id: int, *, db_path: str = DB_PATH) -> int:
    async with connect_db(db_path) as conn:
        cursor = await conn.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
        await conn.commit()
        return cursor.rowcount or 0


async def persist_subscription_lifecycle_state(
    subscription_id: int,
    status: str,
    reason: str | None,
    progress_current: int,
    progress_total: int,
    episode_state: dict | None = None,
    *,
    db_path: str = DB_PATH,
) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute(
            """
            UPDATE subscriptions
            SET status = ?, completion_reason = ?, progress_current = ?, progress_total = ?,
                episode_state_json = ?,
                completed_at = CASE
                    WHEN ? = 'completed' AND completed_at IS NULL THEN CURRENT_TIMESTAMP
                    WHEN ? != 'completed' THEN NULL
                    ELSE completed_at
                END,
                enabled = CASE WHEN ? = 'completed' THEN 0 ELSE enabled END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                reason,
                progress_current,
                progress_total,
                json.dumps(episode_state or {}, ensure_ascii=False, separators=(",", ":")),
                status,
                status,
                status,
                subscription_id,
            ),
        )
        await conn.commit()


async def list_subscription_lifecycle_rows(
    subscription_ids: list[int],
    *,
    db_path: str = DB_PATH,
) -> list[dict]:
    if not subscription_ids:
        return []
    placeholders = ",".join("?" for _ in subscription_ids)
    async with connect_db(db_path, row_factory=aiosqlite.Row) as conn:
        async with conn.execute(
            f"""
            SELECT id, keyword, media_type, tmdb_id, tmdb_type, year, enabled, status, target_seasons_json
            FROM subscriptions
            WHERE id IN ({placeholders})
            """,
            subscription_ids,
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def list_subscription_state_rows(*, db_path: str = DB_PATH) -> list[dict]:
    async with connect_db(db_path, row_factory=aiosqlite.Row) as conn:
        async with conn.execute(
            """
            SELECT id, keyword, media_type, tmdb_id, tmdb_type, year, enabled, status,
                   completed_at, progress_current, progress_total, episode_state_json
            FROM subscriptions
            """
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def list_local_subscription_candidate_rows(
    keyword: str,
    *,
    limit: int,
    db_path: str = DB_PATH,
) -> list[dict]:
    like_keyword = f"%{keyword}%"
    async with connect_db(db_path, row_factory=aiosqlite.Row) as conn:
        async with conn.execute(
            """
            SELECT *
            FROM messages
            WHERE (
                (resource_url IS NOT NULL AND resource_url != '')
                OR EXISTS (
                    SELECT 1 FROM links resource_links
                    WHERE resource_links.message_id = messages.id
                )
            )
            AND (
                title LIKE ?
                OR description LIKE ?
                OR raw_text LIKE ?
            )
            ORDER BY publish_date DESC, id DESC
            LIMIT ?
            """,
            (like_keyword, like_keyword, like_keyword, limit),
        ) as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]

        message_ids = [row["id"] for row in rows if row.get("id")]
        links_by_message_id = {message_id: [] for message_id in message_ids}
        if message_ids:
            placeholders = ",".join("?" for _ in message_ids)
            async with conn.execute(
                f"SELECT * FROM links WHERE message_id IN ({placeholders})",
                tuple(message_ids),
            ) as links_cursor:
                for link_row in await links_cursor.fetchall():
                    links_by_message_id[link_row["message_id"]].append(dict(link_row))

    for row in rows:
        row["links"] = links_by_message_id.get(row.get("id"), [])
    return rows


async def get_latest_active_subscription_checked_at_value(*, db_path: str = DB_PATH) -> str | None:
    async with connect_db(db_path) as conn:
        async with conn.execute(
            """
            SELECT MAX(last_checked_at)
            FROM subscriptions
            WHERE COALESCE(enabled, 1) = 1
              AND COALESCE(status, 'active') != 'completed'
            """
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None
