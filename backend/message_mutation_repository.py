# -*- coding: utf-8 -*-

from config import DB_PATH
from db import connect_db


async def update_message_poster_fields(
    *,
    message_id: int,
    image_url: str | None,
    tmdb_id: int | None,
    tmdb_type: str | None,
    year: int | None,
    db_path: str = DB_PATH,
) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute(
            """
            UPDATE messages
            SET image_url = ?, tmdb_id = ?, tmdb_type = ?, year = ?
            WHERE id = ?
            """,
            (image_url, tmdb_id, tmdb_type, year, message_id),
        )
        await conn.commit()


async def clear_messages_by_channel(channel_name: str, *, db_path: str = DB_PATH) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute(
            "DELETE FROM links WHERE message_id IN (SELECT id FROM messages WHERE channel_name = ?)",
            (channel_name,),
        )
        await conn.execute("DELETE FROM messages WHERE channel_name = ?", (channel_name,))
        await conn.commit()


async def clear_all_messages(*, db_path: str = DB_PATH) -> None:
    async with connect_db(db_path) as conn:
        await conn.execute("DELETE FROM messages")
        await conn.execute("DELETE FROM links")
        await conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('messages', 'links')")
        await conn.commit()
