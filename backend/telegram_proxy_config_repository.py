# -*- coding: utf-8 -*-

from config import DB_PATH
from db import connect_db


async def get_config_value(key: str, db_path: str = DB_PATH) -> str | None:
    async with connect_db(db_path) as conn:
        async with conn.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def write_config_value(key: str, value: str, db_path: str = DB_PATH) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        await conn.commit()


async def delete_config_value(key: str, db_path: str = DB_PATH) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute("DELETE FROM config WHERE key = ?", (key,))
        await conn.commit()
