# -*- coding: utf-8 -*-
from db import connect_db


async def update_message_posters(db_path: str, message_ids: list[int], poster_url: str | None) -> int:
    if not poster_url or not message_ids:
        return 0
    updates = [(poster_url, msg_id) for msg_id in message_ids]
    async with connect_db(db_path, timeout=30.0) as conn:
        await conn.executemany("UPDATE messages SET image_url = ? WHERE id = ?", updates)
        await conn.commit()
    return len(updates)
