# -*- coding: utf-8 -*-
from config import DB_PATH
from message_mutation_repository import (
    clear_all_messages,
    clear_messages_by_channel,
    update_message_poster_fields,
)
import message_query_service
from schemas import ScrapeRequest, UpdatePosterRequest


async def update_message_poster_payload(request: UpdatePosterRequest, *, db_path: str = DB_PATH) -> dict:
    await update_message_poster_fields(
        message_id=request.message_id,
        image_url=request.image_url,
        tmdb_id=request.tmdb_id,
        tmdb_type=request.tmdb_type,
        year=request.year,
        db_path=db_path,
    )
    return {"status": "success", "message": "海报已更新"}


async def clear_messages_payload(request: ScrapeRequest | None = None, *, db_path: str = DB_PATH) -> dict:
    if request and request.channel_name:
        channel_name = request.channel_name
        await clear_messages_by_channel(channel_name, db_path=db_path)
        message = f"频道 '{channel_name}' 的消息已清空。"
    else:
        await clear_all_messages(db_path=db_path)
        message = "所有消息已清空。"
    message_query_service.clear_sources_cache()
    return {"message": message}
