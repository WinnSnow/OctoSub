# -*- coding: utf-8 -*-
import asyncio

import aiosqlite

from config import DB_PATH
from db import connect_db


async def fetch_active_subscriptions(
    subscription_id: int | None = None,
    db_path: str = DB_PATH,
) -> list[tuple]:
    params = []
    where_subscription = ""
    if subscription_id is not None:
        where_subscription = " AND id = ?"
        params.append(subscription_id)

    async with connect_db(db_path) as conn:
        async with conn.execute("PRAGMA table_info(subscriptions)") as info_cursor:
            columns = {row[1] for row in await info_cursor.fetchall()}
        target_seasons_select = "target_seasons_json" if "target_seasons_json" in columns else "NULL AS target_seasons_json"
        async with conn.execute(
            f"""
            SELECT id, keyword, quality_filter, media_type, tmdb_id, tmdb_type, year,
                   auto_transfer, min_confidence, {target_seasons_select}
            FROM subscriptions
            WHERE COALESCE(enabled, 1) = 1
              AND COALESCE(status, 'active') = 'active'
              {where_subscription}
            """,
            params,
        ) as cursor:
            return await cursor.fetchall()


async def mark_subscription_checked(subscription_id: int, db_path: str = DB_PATH, retries: int = 3) -> None:
    for attempt in range(retries + 1):
        try:
            async with connect_db(db_path, timeout=60.0) as conn:
                await conn.execute(
                    "UPDATE subscriptions SET last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (subscription_id,),
                )
                await conn.commit()
            return
        except aiosqlite.OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt >= retries:
                raise
            await asyncio.sleep(0.25 * (attempt + 1))
