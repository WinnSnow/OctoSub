# -*- coding: utf-8 -*-
import json

from fastapi import HTTPException

from config import DB_PATH, SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE
from schemas import SubscriptionPayload, SubscriptionStatusUpdate
from subscription_repository import (
    delete_subscription,
    insert_subscription,
    list_subscription_ids,
    list_subscription_rows,
    update_subscription,
    update_subscription_status,
)
from subscription_schedule_state_service import db_datetime_to_local_iso


def normalize_subscription_payload(payload: SubscriptionPayload) -> tuple[str, str | None, str]:
    keyword = payload.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="订阅关键词不能为空。")

    media_type = payload.media_type.strip().lower()
    if media_type not in {"tv", "movie"}:
        raise HTTPException(status_code=400, detail="媒体类型只能是 tv 或 movie。")

    quality_filter = payload.quality_filter.strip() if payload.quality_filter else None
    return keyword, quality_filter, media_type


def subscription_row_to_dict(row) -> dict:
    enabled = bool(row[10]) if len(row) > 10 else True
    raw_status = row[14] if len(row) > 14 else "active"
    status = "paused" if raw_status != "completed" and not enabled else raw_status
    try:
        episode_state = json.loads(row[19] if len(row) > 19 and row[19] else "{}")
        if not isinstance(episode_state, dict):
            episode_state = {}
    except Exception:
        episode_state = {}
    try:
        target_seasons = json.loads(row[20] if len(row) > 20 and row[20] else "null")
        if target_seasons is not None:
            target_seasons = sorted({int(item) for item in target_seasons if int(item) > 0})
    except Exception:
        target_seasons = None
    return {
        "id": row[0],
        "keyword": row[1],
        "quality_filter": row[2],
        "media_type": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "tmdb_id": row[6] if len(row) > 6 else None,
        "tmdb_type": row[7] if len(row) > 7 else None,
        "year": row[8] if len(row) > 8 else None,
        "poster_url": row[9] if len(row) > 9 else None,
        "enabled": enabled,
        "auto_transfer": bool(row[11]) if len(row) > 11 else True,
        "min_confidence": row[12] if len(row) > 12 else SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE,
        "last_checked_at": db_datetime_to_local_iso(row[13] if len(row) > 13 else None),
        "status": status,
        "completed_at": row[15] if len(row) > 15 else None,
        "completion_reason": row[16] if len(row) > 16 else None,
        "progress_current": row[17] if len(row) > 17 else 0,
        "progress_total": row[18] if len(row) > 18 else 0,
        "episode_state": episode_state,
        "target_seasons": target_seasons,
        "douban_id": row[21] if len(row) > 21 else None,
        "douban_url": row[22] if len(row) > 22 else None,
        "douban_rating": row[23] if len(row) > 23 else None,
        "metadata_source": row[24] if len(row) > 24 else None,
    }


async def get_subscriptions_payload(proxy_config: dict | None = None) -> list[dict]:
    rows = await list_subscription_rows(db_path=DB_PATH)
    return [subscription_row_to_dict(row) for row in rows]


async def get_subscription_ids_payload(subscription_id: int | None = None) -> list[int]:
    return await list_subscription_ids(subscription_id=subscription_id, db_path=DB_PATH)


async def add_subscription_payload(payload: SubscriptionPayload) -> dict:
    keyword, quality_filter, media_type = normalize_subscription_payload(payload)
    row = await insert_subscription(
        payload,
        keyword=keyword,
        quality_filter=quality_filter,
        media_type=media_type,
        db_path=DB_PATH,
    )
    return subscription_row_to_dict(row)


async def update_subscription_payload(subscription_id: int, payload: SubscriptionPayload) -> dict:
    keyword, quality_filter, media_type = normalize_subscription_payload(payload)
    row = await update_subscription(
        subscription_id,
        payload,
        keyword=keyword,
        quality_filter=quality_filter,
        media_type=media_type,
        db_path=DB_PATH,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="订阅不存在。")
    return subscription_row_to_dict(row)


async def update_subscription_status_payload(subscription_id: int, payload: SubscriptionStatusUpdate) -> dict:
    row = await update_subscription_status(subscription_id, payload.status, db_path=DB_PATH)
    if row is None:
        raise HTTPException(status_code=404, detail="订阅不存在。")
    return subscription_row_to_dict(row)


async def delete_subscription_payload(subscription_id: int) -> dict:
    deleted = await delete_subscription(subscription_id, db_path=DB_PATH)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="订阅不存在。")
    return {"message": "订阅删除成功"}
