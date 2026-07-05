# -*- coding: utf-8 -*-

from config import DB_PATH
from db import connect_db
from pending_transfer_status import PENDING_TRANSFER_STATUS_PENDING


async def count_rows(conn, sql: str, params: tuple = ()) -> int:
    async with conn.execute(sql, params) as cursor:
        row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def load_jellyfin_index_counts(conn) -> dict:
    try:
        async with conn.execute(
            "SELECT media_type, COUNT(*) AS count FROM jellyfin_library_items GROUP BY media_type"
        ) as cursor:
            rows = await cursor.fetchall()
    except Exception:
        rows = []
    counts = {row[0]: int(row[1] or 0) for row in rows}
    try:
        async with conn.execute(
            "SELECT value FROM system_config WHERE key = 'jellyfin_library_index_last_sync_at'"
        ) as cursor:
            sync_row = await cursor.fetchone()
    except Exception:
        sync_row = None
    return {
        "total": sum(counts.values()),
        "movies": counts.get("movie", 0),
        "series": counts.get("series", 0),
        "episodes": counts.get("episode", 0),
        "last_sync_at": sync_row[0] if sync_row else None,
    }


async def load_dashboard_counts(db_path: str = DB_PATH) -> dict:
    async with connect_db(db_path) as conn:
        return {
            "messages_total": await count_rows(conn, "SELECT COUNT(*) FROM messages"),
            "links_total": await count_rows(conn, "SELECT COUNT(*) FROM links"),
            "jellyfin_index": await load_jellyfin_index_counts(conn),
            "subscriptions_total": await count_rows(conn, "SELECT COUNT(*) FROM subscriptions"),
            "subscriptions_active": await count_rows(
                conn,
                "SELECT COUNT(*) FROM subscriptions WHERE enabled = 1 AND COALESCE(status, 'active') != 'completed'",
            ),
            "history_total": await count_rows(conn, "SELECT COUNT(*) FROM download_history"),
            "history_success": await count_rows(conn, "SELECT COUNT(*) FROM download_history WHERE status = 'success'"),
            "pending_transfers": await count_rows(
                conn,
                "SELECT COUNT(*) FROM pending_transfers WHERE status = ?",
                (PENDING_TRANSFER_STATUS_PENDING,),
            ),
        }
