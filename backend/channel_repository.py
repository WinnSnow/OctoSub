# -*- coding: utf-8 -*-

from config import DB_PATH
from db import connect_db


async def list_channel_rows(*, db_path: str = DB_PATH, order_by_id: bool = False) -> list[dict]:
    order_sql = " ORDER BY id ASC" if order_by_id else ""
    async with connect_db(db_path) as conn:
        async with conn.execute(f"SELECT id, url FROM channels{order_sql}") as cursor:
            return [{"id": row[0], "url": row[1]} for row in await cursor.fetchall()]


async def insert_channel(url: str, *, db_path: str = DB_PATH) -> int:
    async with connect_db(db_path) as conn:
        await conn.execute("INSERT INTO channels (url) VALUES (?)", (url,))
        await conn.commit()
        async with conn.execute("SELECT last_insert_rowid()") as cursor:
            return int((await cursor.fetchone())[0])


async def delete_channel(channel_id: int, *, db_path: str = DB_PATH) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        await conn.commit()
