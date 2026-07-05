from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

import channel_service
from config import DB_PATH, PUBLIC_SEARCH_CHANNELS
from library_state_service import resolve_library_states_for_items
import message_media_service
import message_mutation_service
import message_poster_task_service
import message_query_service
from poster_match_service import match_single_message_poster
from poster_service import manual_tmdb_search
from tmdb_service import fetch_tmdb_media_detail, fetch_tmdb_tv_detail
from scrape_service import trigger_scrape_payload
from schemas import Channel, ManualSearchRequest, ScrapeRequest, SingleMatchRequest, UpdatePosterRequest
from telegram_service import get_active_proxy_config


router = APIRouter()
_build_fts_match_query = message_query_service._build_fts_match_query
_selected_channels = message_query_service._selected_channels
_apply_channel_filter = message_query_service._apply_channel_filter
search_douban = message_media_service.search_douban
annotate_items_with_subscription_state = message_media_service.annotate_items_with_subscription_state
annotate_tmdb_search_items_with_jellyfin_state = message_media_service.annotate_tmdb_search_items_with_jellyfin_state
create_task = message_poster_task_service.create_task
match_posters_for_messages = message_poster_task_service.match_posters_for_messages
enqueue_heavy_task = message_poster_task_service.enqueue_heavy_task


@router.post("/api/tmdb/search")
async def manual_search_tmdb(request: ManualSearchRequest):
    return await manual_tmdb_search(request.query, get_active_proxy_config())


@router.get("/api/media/search")
async def manual_search_media(
    keyword: Annotated[str, Query(min_length=1)],
    media_type: Annotated[str | None, Query(pattern="^(movie|tv)$")] = None,
):
    return await message_media_service.manual_search_media_payload(keyword, media_type)


@router.get("/api/tmdb/tv/{tmdb_id}")
async def get_tmdb_tv_detail(tmdb_id: int):
    return await fetch_tmdb_tv_detail(tmdb_id, get_active_proxy_config())


@router.get("/api/tmdb/{media_type}/{tmdb_id}")
async def get_tmdb_media_detail(media_type: str, tmdb_id: int):
    return await fetch_tmdb_media_detail(media_type, tmdb_id, get_active_proxy_config())


@router.post("/api/messages/update_poster")
async def update_message_poster(request: UpdatePosterRequest):
    return await message_mutation_service.update_message_poster_payload(request, db_path=DB_PATH)


@router.get("/api/channels")
async def get_channels():
    return await channel_service.list_channels(db_path=DB_PATH)


@router.get("/api/public-channels")
async def get_public_channels():
    channel_service.PUBLIC_SEARCH_CHANNELS = PUBLIC_SEARCH_CHANNELS
    return await channel_service.list_public_channels(db_path=DB_PATH)


@router.post("/api/channels")
async def add_channel(channel: Channel):
    return await channel_service.add_channel_payload(channel, db_path=DB_PATH)


@router.delete("/api/channels/{channel_id}")
async def delete_channel(channel_id: int):
    return await channel_service.delete_channel_payload(channel_id, db_path=DB_PATH)


@router.post("/api/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks, request: ScrapeRequest | None = None):
    return await trigger_scrape_payload(request.channel_name if request else None)


@router.get("/api/messages")
async def get_messages(
    page: int = 1,
    limit: int = 25,
    channel_name: str | None = None,
    channel_names: Annotated[list[str] | None, Query()] = None,
    search: str | None = None,
):
    return await message_query_service.get_local_messages_payload(
        page=page,
        limit=limit,
        channel_name=channel_name,
        channel_names=channel_names,
        search=search,
        db_path=DB_PATH,
    )


@router.post("/api/library-states")
async def get_library_states(payload: dict):
    items = payload.get("items") if isinstance(payload, dict) else None
    if items is None:
        items = []
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="items 必须是数组")
    return {"states": await resolve_library_states_for_items(items)}


@router.post("/api/messages/clear")
async def clear_messages(request: ScrapeRequest | None = None):
    return await message_mutation_service.clear_messages_payload(request, db_path=DB_PATH)


@router.post("/api/messages/match_poster_single")
async def match_poster_single(request: SingleMatchRequest):
    return await match_single_message_poster(request.message_id, get_active_proxy_config())


@router.post("/api/messages/match_posters")
async def match_posters(background_tasks: BackgroundTasks):
    return await message_poster_task_service.match_posters_task(background_tasks)
