# -*- coding: utf-8 -*-

from config import DB_PATH
from db import connect_db
from download_history_status import DOWNLOAD_STATUS_SUBMITTED


async def record_download_history_row(
    *,
    subscription_id: int | None,
    title: str | None,
    fingerprint: str,
    link: str,
    status: str,
    message: str | None = None,
    db_path: str = DB_PATH,
) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute(
            """
            INSERT OR IGNORE INTO download_history
                (subscription_id, title, fingerprint, link, status, callback_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (subscription_id, title, fingerprint, link, status, message),
        )
        await conn.execute(
            """
            UPDATE download_history
            SET status = ?,
                title = COALESCE(?, title),
                callback_message = COALESCE(?, callback_message),
                updated_at = CURRENT_TIMESTAMP
            WHERE fingerprint = ? OR link = ?
            """,
            (status, title, message, fingerprint, link),
        )
        await conn.commit()


async def reserve_download_history_row(
    *,
    subscription_id: int | None,
    title: str | None,
    fingerprint: str,
    link: str,
    db_path: str = DB_PATH,
) -> tuple[bool, int | None]:
    async with connect_db(db_path) as conn:
        cursor = await conn.execute(
            """
            INSERT OR IGNORE INTO download_history
                (subscription_id, title, fingerprint, link, status, callback_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (subscription_id, title, fingerprint, link, DOWNLOAD_STATUS_SUBMITTED, "转存任务提交中"),
        )
        await conn.commit()
        if cursor.rowcount:
            async with conn.execute("SELECT last_insert_rowid()") as id_cursor:
                row = await id_cursor.fetchone()
            return True, row[0] if row else None

        if title:
            await conn.execute(
                """
                UPDATE download_history
                SET title = COALESCE(NULLIF(title, ''), ?)
                WHERE fingerprint = ? OR link = ?
                """,
                (title, fingerprint, link),
            )
            await conn.commit()
        async with conn.execute(
            "SELECT id FROM download_history WHERE fingerprint = ? OR link = ?",
            (fingerprint, link),
        ) as cursor:
            row = await cursor.fetchone()
        return False, row[0] if row else None


async def insert_pending_transfer_row(
    *,
    subscription_id: int | None,
    result_id: str,
    title: str,
    link: str,
    password: str | None,
    confidence: float,
    match_reason: str | None,
    payload_json: str,
    db_path: str = DB_PATH,
) -> tuple[bool, int | None]:
    async with connect_db(db_path) as conn:
        cursor = await conn.execute(
            """
            INSERT OR IGNORE INTO pending_transfers
                (subscription_id, result_id, title, link, password, confidence, match_reason, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                result_id,
                title,
                link,
                password,
                confidence,
                match_reason,
                payload_json,
            ),
        )
        await conn.commit()
        return bool(cursor.rowcount), cursor.lastrowid if cursor.rowcount else None


async def load_pending_transfer_identity_row(
    *,
    subscription_id: int | None,
    result_id: str,
    link: str,
    db_path: str = DB_PATH,
) -> tuple | None:
    async with connect_db(db_path) as conn:
        async with conn.execute(
            """
            SELECT id, status
            FROM pending_transfers
            WHERE (subscription_id = ? OR (subscription_id IS NULL AND ? IS NULL))
              AND result_id = ?
              AND link = ?
            LIMIT 1
            """,
            (subscription_id, subscription_id, result_id, link),
        ) as existing_cursor:
            return await existing_cursor.fetchone()


async def list_submitted_download_history_link_candidates(
    *,
    link: str,
    share_code: str | None = None,
    db_path: str = DB_PATH,
) -> list[tuple]:
    async with connect_db(db_path) as conn:
        if share_code:
            async with conn.execute(
                """
                SELECT id, link
                FROM download_history
                WHERE status = ?
                  AND (link = ? OR link LIKE ?)
                """,
                (DOWNLOAD_STATUS_SUBMITTED, link, f"%/s/{share_code}%"),
            ) as cursor:
                return await cursor.fetchall()
        async with conn.execute(
            """
            SELECT id, link
            FROM download_history
            WHERE status = ?
              AND link = ?
            """,
            (DOWNLOAD_STATUS_SUBMITTED, link),
        ) as cursor:
            return await cursor.fetchall()


async def update_download_history_callback_for_ids(
    history_ids: list[int],
    *,
    status: str,
    message: str,
    db_path: str = DB_PATH,
) -> int:
    if not history_ids:
        return 0
    placeholders = ",".join("?" for _ in history_ids)
    async with connect_db(db_path) as conn:
        cursor = await conn.execute(
            f"""
            UPDATE download_history
            SET status = ?,
                callback_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            (status, message, *history_ids),
        )
        await conn.commit()
        return cursor.rowcount or 0
