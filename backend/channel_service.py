# -*- coding: utf-8 -*-
import sqlite3

from fastapi import HTTPException

from channel_repository import delete_channel, insert_channel, list_channel_rows
from config import DB_PATH, PUBLIC_SEARCH_CHANNELS
from schemas import Channel
from utils import normalize_channel_url


async def list_channels(*, db_path: str = DB_PATH) -> list[dict]:
    return await list_channel_rows(db_path=db_path)


async def list_public_channels(*, db_path: str = DB_PATH) -> list[dict]:
    public_items = []
    seen = set()
    for channel in PUBLIC_SEARCH_CHANNELS:
        normalized = normalize_channel_url(channel)
        if normalized and normalized not in seen:
            seen.add(normalized)
            public_items.append({"id": f"env:{normalized}", "url": normalized, "source": "env"})

    for row in await list_channel_rows(db_path=db_path, order_by_id=True):
        normalized = normalize_channel_url(row["url"])
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        public_items.append({"id": f"db:{row['id']}", "url": normalized, "source": "channels"})
    return public_items


async def add_channel_payload(channel: Channel, *, db_path: str = DB_PATH) -> dict:
    normalized_url = normalize_channel_url(channel.url)
    if not normalized_url:
        raise HTTPException(status_code=400, detail="无效的频道 URL 或用户名。")
    try:
        channel_id = await insert_channel(normalized_url, db_path=db_path)
        return {"id": channel_id, "url": normalized_url}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"频道 '{normalized_url}' 已存在。") from None


async def delete_channel_payload(channel_id: int, *, db_path: str = DB_PATH) -> dict:
    await delete_channel(channel_id, db_path=db_path)
    return {"message": "频道删除成功"}
