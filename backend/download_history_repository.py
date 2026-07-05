# -*- coding: utf-8 -*-
import sqlite3

from config import DB_PATH
from db import connect_db
from download_history_status import (
    DOWNLOAD_STATUS_FAILED,
    DOWNLOAD_STATUS_SUBMITTED,
)


async def table_has_column(conn, table_name: str, column_name: str) -> bool:
    async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
        return column_name in {row[1] for row in await cursor.fetchall()}


async def count_download_history_by_status(
    status: str,
    *,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> int:
    async with connect_db(db_path) as conn:
        has_user_id = await table_has_column(conn, "download_history", "user_id")
        user_filter = "AND (? IS NULL OR user_id = ?)" if has_user_id else ""
        params = (user_id, user_id) if has_user_id else ()
        async with conn.execute(
            f"""
            SELECT COUNT(*)
            FROM download_history
            WHERE status = ?
              {user_filter}
            """,
            (status, *params),
        ) as cursor:
            row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def list_download_history_rows(
    *,
    subscription_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 100,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> tuple[int, list, list]:
    params: list = []
    where_clauses = []
    if subscription_id is not None:
        where_clauses.append("h.subscription_id = ?")
        params.append(subscription_id)
    if status:
        where_clauses.append("h.status = ?")
        params.append(status)
    offset = (page - 1) * limit

    async with connect_db(db_path) as conn:
        if user_id is not None and await table_has_column(conn, "download_history", "user_id"):
            where_clauses.append("h.user_id = ?")
            params.append(user_id)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        async with conn.execute(
            f"""
            SELECT COUNT(*)
            FROM download_history h
            LEFT JOIN subscriptions s ON h.subscription_id = s.id
            {where_clause}
            """,
            params,
        ) as cursor:
            total = (await cursor.fetchone())[0]

        async with conn.execute(
            f"""
            SELECT h.status, COUNT(*)
            FROM download_history h
            LEFT JOIN subscriptions s ON h.subscription_id = s.id
            {where_clause}
            GROUP BY h.status
            """,
            params,
        ) as cursor:
            status_rows = await cursor.fetchall()

        async with conn.execute(
            f"""
            SELECT h.id, h.subscription_id, h.title, h.fingerprint, h.link, h.status,
                   h.created_at, h.callback_message, h.updated_at, s.keyword
            FROM download_history h
            LEFT JOIN subscriptions s ON h.subscription_id = s.id
            {where_clause}
            ORDER BY h.id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ) as cursor:
            rows = await cursor.fetchall()

    return int(total or 0), status_rows, rows


async def update_download_history_status(
    history_id: int,
    status: str,
    message: str | None = None,
    *,
    from_status: str | None = None,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> int:
    async with connect_db(db_path) as conn:
        has_user_id = await table_has_column(conn, "download_history", "user_id")
        filters = ["id = ?"]
        params: list = [history_id]
        if from_status is not None:
            filters.append("status = ?")
            params.append(from_status)
        if user_id is not None and has_user_id:
            filters.append("user_id = ?")
            params.append(user_id)
        cursor = await conn.execute(
            f"""
            UPDATE download_history
            SET status = ?,
                callback_message = COALESCE(?, callback_message),
                updated_at = CURRENT_TIMESTAMP
            WHERE {' AND '.join(filters)}
            """,
            (status, message, *params),
        )
        await conn.commit()
        return cursor.rowcount or 0


async def load_download_history_for_retry(
    history_id: int,
    *,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> tuple | None:
    async with connect_db(db_path) as conn:
        has_user_id = await table_has_column(conn, "download_history", "user_id")
        user_filter = "AND user_id = ?" if user_id is not None and has_user_id else ""
        user_params = [user_id] if user_id is not None and has_user_id else []
        async with conn.execute(
            f"""
            SELECT id, subscription_id, title, fingerprint, link, status
            FROM download_history
            WHERE id = ?
              {user_filter}
            """,
            (history_id, *user_params),
        ) as cursor:
            return await cursor.fetchone()


async def load_successful_subscription_transfer_row(
    history_id: int,
    *,
    db_path: str = DB_PATH,
) -> tuple | None:
    async with connect_db(db_path) as conn:
        async with conn.execute(
            """
            SELECT h.id, h.subscription_id, h.title, h.fingerprint, h.link, h.status,
                   s.keyword, s.year, s.media_type, s.tmdb_type
            FROM download_history h
            LEFT JOIN subscriptions s ON h.subscription_id = s.id
            WHERE h.id = ?
            """,
            (history_id,),
        ) as cursor:
            return await cursor.fetchone()


async def reserve_failed_download_history_retry(
    history_id: int,
    *,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> int:
    return await update_download_history_status(
        history_id,
        DOWNLOAD_STATUS_SUBMITTED,
        "转存重试已提交",
        from_status=DOWNLOAD_STATUS_FAILED,
        user_id=user_id,
        db_path=db_path,
    )


async def insert_download_history(
    *,
    subscription_id: int | None,
    title: str | None,
    fingerprint: str,
    link: str,
    status: str,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> int:
    try:
        async with connect_db(db_path) as conn:
            if user_id is not None and await table_has_column(conn, "download_history", "user_id"):
                await conn.execute(
                    """
                    INSERT INTO download_history (user_id, subscription_id, title, fingerprint, link, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, subscription_id, title, fingerprint, link, status),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO download_history (subscription_id, title, fingerprint, link, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (subscription_id, title, fingerprint, link, status),
                )
            await conn.commit()
            async with conn.execute("SELECT last_insert_rowid()") as cursor:
                return (await cursor.fetchone())[0]
    except sqlite3.IntegrityError:
        raise


async def download_history_exists_by_fingerprint_or_link(
    fingerprint: str,
    link: str,
    *,
    db_path: str = DB_PATH,
) -> bool:
    async with connect_db(db_path) as conn:
        async with conn.execute(
            "SELECT id FROM download_history WHERE fingerprint = ? OR link = ?",
            (fingerprint, link),
        ) as cursor:
            return await cursor.fetchone() is not None
