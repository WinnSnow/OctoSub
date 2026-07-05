# -*- coding: utf-8 -*-
from fastapi import HTTPException

from config import DB_PATH
from message_extraction_service import (
    extract_links,
    extract_links_from_telegraph,
    filter_message_text,
    is_promotional_message,
    parse_structured_format,
)
from poster_service import fetch_movie_poster
from scrape_channel_service import scrape_channel as _scrape_channel
from scrape_link_collector_service import collect_resource_links, dedupe_preserve_order
from scrape_link_collector_service import extract_link_candidates as _extract_link_candidates
from scrape_link_collector_service import has_resource_link_entrypoint as _has_resource_link_entrypoint
from scrape_link_collector_service import resolve_intermediate_resource_links
from scrape_poster_backfill_service import schedule_poster_backfill
from scrape_retry_service import (
    retry_missing_links_payload as _retry_missing_links_payload,
    retry_single_message as _retry_single_message,
)
from scrape_telegram_readiness_service import (
    TelegramScrapeUnavailable,
    ensure_telegram_ready as _ensure_telegram_ready,
)
from scrape_task_service import trigger_scrape_payload as _trigger_scrape_payload
from task_service import TASK_PROGRESS, create_task, enqueue_heavy_task, get_task, is_cancel_requested, update_task
from telegram_service import get_active_proxy_config, get_telegram_client
from utils import append_query_param as _append_query_param


async def _collect_resource_links(message) -> list[str]:
    return await collect_resource_links(
        message,
        get_active_proxy_config(),
        extract_links_fn=extract_links,
        extract_links_from_telegraph_fn=extract_links_from_telegraph,
        append_query_param_fn=_append_query_param,
    )


def _extract_link_candidates_for_scrape(message, *, text: str | None = None) -> dict:
    return _extract_link_candidates(
        message,
        extract_links_fn=extract_links,
        append_query_param_fn=_append_query_param,
        text=text,
    )


async def _resolve_intermediate_links(intermediate_urls: list[str], stats: dict | None = None) -> list[str]:
    return await resolve_intermediate_resource_links(
        intermediate_urls,
        get_active_proxy_config(),
        extract_links_from_telegraph_fn=extract_links_from_telegraph,
        append_query_param_fn=_append_query_param,
        stats=stats,
    )


def has_resource_link_entrypoint(message) -> bool:
    return _has_resource_link_entrypoint(message, extract_links_fn=extract_links)


async def ensure_telegram_ready():
    return await _ensure_telegram_ready(get_client_fn=get_telegram_client)


def _schedule_poster_backfill(message_ids: list[int]) -> None:
    schedule_poster_backfill(message_ids)


async def retry_single_message(channel_name: str, message_id: int) -> bool:
    return await _retry_single_message(
        channel_name,
        message_id,
        ensure_telegram_ready_fn=ensure_telegram_ready,
        collect_resource_links_fn=_collect_resource_links,
        fetch_movie_poster_fn=fetch_movie_poster,
        db_path=DB_PATH,
    )


async def retry_missing_links_payload(channel_name: str) -> dict:
    return await _retry_missing_links_payload(
        channel_name,
        retry_single_message_fn=retry_single_message,
        db_path=DB_PATH,
    )


async def get_task_progress_payload(task_id: str) -> dict:
    return get_task(task_id)


async def scrape_channel(channel_name: str, task_id: str | None = None) -> list[int]:
    return await _scrape_channel(
        channel_name,
        task_id,
        ensure_telegram_ready_fn=ensure_telegram_ready,
        collect_resource_links_fn=_collect_resource_links,
        extract_link_candidates_fn=_extract_link_candidates_for_scrape,
        resolve_intermediate_links_fn=_resolve_intermediate_links,
        db_path=DB_PATH,
        task_progress=TASK_PROGRESS,
        update_task_fn=update_task,
        parse_structured_format_fn=parse_structured_format,
        filter_message_text_fn=filter_message_text,
        is_promotional_message_fn=is_promotional_message,
        dedupe_preserve_order_fn=dedupe_preserve_order,
        has_resource_link_entrypoint_fn=has_resource_link_entrypoint,
        should_cancel_fn=is_cancel_requested,
    )


async def trigger_scrape_payload(channel_name: str | None) -> dict:
    try:
        return await _trigger_scrape_payload(
            channel_name,
            ensure_telegram_ready_fn=ensure_telegram_ready,
            scrape_channel_fn=scrape_channel,
            schedule_poster_backfill_fn=_schedule_poster_backfill,
            db_path=DB_PATH,
            create_task_fn=create_task,
            enqueue_task_fn=enqueue_heavy_task,
        )
    except TelegramScrapeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
