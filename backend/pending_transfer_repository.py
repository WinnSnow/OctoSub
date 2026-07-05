# -*- coding: utf-8 -*-
from config import DB_PATH
from db import connect_db
from pending_transfer_status import (
    PENDING_TRANSFER_STATUS_PENDING,
    PENDING_TRANSFER_STATUS_REJECTED,
    PENDING_TRANSFER_STATUS_RESOLVED,
)


async def table_has_column(conn, table_name: str, column_name: str) -> bool:
    async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
        return column_name in {row[1] for row in await cursor.fetchall()}


async def load_pending_payload_json(
    pending_id: int,
    *,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> str | None:
    try:
        async with connect_db(db_path) as conn:
            has_user_id = await table_has_column(conn, "pending_transfers", "user_id")
            user_filter = "AND user_id = ?" if user_id is not None and has_user_id else ""
            user_params = [user_id] if user_id is not None and has_user_id else []
            async with conn.execute(
                f"SELECT payload_json FROM pending_transfers WHERE id = ? AND status = ? {user_filter}",
                (pending_id, PENDING_TRANSFER_STATUS_PENDING, *user_params),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None


async def load_pending_transfer_for_approval(
    pending_id: int,
    *,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> tuple | None:
    async with connect_db(db_path) as conn:
        has_user_id = await table_has_column(conn, "pending_transfers", "user_id")
        user_filter = "AND user_id = ?" if user_id is not None and has_user_id else ""
        user_params = [user_id] if user_id is not None and has_user_id else []
        async with conn.execute(
            f"""
            SELECT subscription_id, result_id, title, link, password
            FROM pending_transfers
            WHERE id = ? AND status = ? {user_filter}
            """,
            (pending_id, PENDING_TRANSFER_STATUS_PENDING, *user_params),
        ) as cursor:
            return await cursor.fetchone()


async def list_pending_transfer_rows(
    *,
    status: str | None,
    status_all: str,
    subscription_id: int | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    sort: str = "latest",
    limit: int = 100,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> list:
    where_clauses = []
    params: list = []
    if status and status != status_all:
        where_clauses.append("p.status = ?")
        params.append(status)
    if subscription_id is not None:
        where_clauses.append("p.subscription_id = ?")
        params.append(subscription_id)
    if confidence_min is not None:
        where_clauses.append("COALESCE(p.confidence, 0) >= ?")
        params.append(confidence_min)
    if confidence_max is not None:
        where_clauses.append("COALESCE(p.confidence, 0) <= ?")
        params.append(confidence_max)
    order_sql = {
        "confidence_asc": "COALESCE(p.confidence, 0) ASC, p.id DESC",
        "confidence_desc": "COALESCE(p.confidence, 0) DESC, p.id DESC",
        "reason": "p.id DESC",
        "latest": "p.id DESC",
    }.get(sort, "p.id DESC")
    params.append(limit)
    async with connect_db(db_path) as conn:
        if user_id is not None and await table_has_column(conn, "pending_transfers", "user_id"):
            where_clauses.append("p.user_id = ?")
            params.insert(len(params) - 1, user_id)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        async with conn.execute(
            f"""
            SELECT p.id, p.subscription_id, p.result_id, p.title, p.link, p.password,
                   p.confidence, p.match_reason, p.status, p.payload_json,
                   p.created_at, p.updated_at, s.keyword, s.media_type, s.year,
                   s.auto_transfer, s.min_confidence, s.quality_filter
            FROM pending_transfers p
            LEFT JOIN subscriptions s ON p.subscription_id = s.id
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ?
            """,
            params,
        ) as cursor:
            return await cursor.fetchall()


async def update_pending_transfer_status(
    pending_id: int,
    status: str,
    *,
    from_status: str | None = None,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> int:
    async with connect_db(db_path) as conn:
        has_user_id = await table_has_column(conn, "pending_transfers", "user_id")
        filters = ["id = ?"]
        params: list = [pending_id]
        if from_status is not None:
            filters.append("status = ?")
            params.append(from_status)
        if user_id is not None and has_user_id:
            filters.append("user_id = ?")
            params.append(user_id)
        cursor = await conn.execute(
            f"""
            UPDATE pending_transfers
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE {' AND '.join(filters)}
            """,
            (status, *params),
        )
        await conn.commit()
        return cursor.rowcount or 0


async def upsert_library_missing_review(
    *,
    subscription_id: int | None,
    result_id: str,
    title: str,
    link: str,
    match_reason: str,
    payload_json: str,
    user_id: int | None = None,
    db_path: str = DB_PATH,
) -> bool:
    async with connect_db(db_path) as conn:
        has_user_id = await table_has_column(conn, "pending_transfers", "user_id")
        if has_user_id:
            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO pending_transfers
                    (user_id, subscription_id, result_id, title, link, confidence, match_reason, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    user_id,
                    subscription_id,
                    result_id,
                    title,
                    link,
                    match_reason,
                    PENDING_TRANSFER_STATUS_PENDING,
                    payload_json,
                ),
            )
            user_filter = "AND (? IS NULL OR user_id = ?)"
            user_params = [user_id, user_id]
        else:
            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO pending_transfers
                    (subscription_id, result_id, title, link, confidence, match_reason, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    subscription_id,
                    result_id,
                    title,
                    link,
                    match_reason,
                    PENDING_TRANSFER_STATUS_PENDING,
                    payload_json,
                ),
            )
            user_filter = ""
            user_params = []
        inserted = bool(cursor.rowcount)
        if not inserted:
            await conn.execute(
                f"""
                UPDATE pending_transfers
                SET status = CASE WHEN status IN (?, ?) THEN status ELSE ? END,
                    title = ?,
                    match_reason = ?,
                    payload_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE (subscription_id = ? OR (subscription_id IS NULL AND ? IS NULL))
                  AND result_id = ?
                  AND link = ?
                  {user_filter}
                """,
                (
                    PENDING_TRANSFER_STATUS_RESOLVED,
                    PENDING_TRANSFER_STATUS_REJECTED,
                    PENDING_TRANSFER_STATUS_PENDING,
                    title,
                    match_reason,
                    payload_json,
                    subscription_id,
                    subscription_id,
                    result_id,
                    link,
                    *user_params,
                ),
            )
        await conn.commit()
        return inserted
