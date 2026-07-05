# -*- coding: utf-8 -*-
import asyncio
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import DB_PATH
from download_history_repository import load_successful_subscription_transfer_row
from jellyfin_library_index_service import refresh_jellyfin_library_index_if_stale
from jellyfin_service import ensure_jellyfin_client
from pending_transfer_repository import (
    load_pending_payload_json,
    update_pending_transfer_status,
    upsert_library_missing_review,
)
from pending_transfer_status import (
    PENDING_TRANSFER_STATUS_PENDING,
    PENDING_TRANSFER_STATUS_REJECTED,
    PENDING_TRANSFER_STATUS_RESOLVED,
)
from structured_logging import log_event
from subscription_lifecycle_service import refresh_subscription_lifecycle_for_ids
from telegram_service import get_active_proxy_config


POST_TRANSFER_LIBRARY_MISSING_REASON = "post_transfer_library_missing"
POST_TRANSFER_LIBRARY_MISSING_LABEL = "转存后未入库"
FIRST_CONFIRM_DELAY_SECONDS = 5 * 60
SECOND_CONFIRM_DELAY_SECONDS = 10 * 60
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def parse_subscription_episode_fingerprint(fingerprint: str | None) -> dict | None:
    if not fingerprint:
        return None
    match = re.search(r"^(?P<subscription_id>\d+):.+?:S(?P<season>\d{1,2})E(?P<episode>\d{1,4})$", fingerprint)
    if not match:
        return None
    return {
        "subscription_id": int(match.group("subscription_id")),
        "season": int(match.group("season")),
        "episode": int(match.group("episode")),
    }


async def load_successful_subscription_transfer(history_id: int, db_path: str = DB_PATH) -> dict | None:
    row = await load_successful_subscription_transfer_row(history_id, db_path=db_path)
    if not row or row[5] != "success" or not row[1]:
        return None
    parsed = parse_subscription_episode_fingerprint(row[3])
    if not parsed:
        return None
    if int(row[1]) != parsed["subscription_id"]:
        return None
    media_type = row[9] or row[8]
    if media_type != "tv":
        return None
    return {
        "history_id": int(row[0]),
        "subscription_id": int(row[1]),
        "title": row[2] or row[6] or "",
        "keyword": row[6] or row[2] or "",
        "year": row[7],
        "fingerprint": row[3],
        "link": row[4],
        "season": parsed["season"],
        "episode": parsed["episode"],
    }


async def jellyfin_has_subscription_episode(transfer: dict) -> bool:
    jellyfin = await ensure_jellyfin_client()
    if not jellyfin:
        return False
    keyword = transfer.get("keyword") or transfer.get("title")
    if not keyword:
        return False
    episodes_by_season = await jellyfin.get_series_episodes_by_season(keyword, transfer.get("year"))
    episodes = episodes_by_season.get(int(transfer["season"]), [])
    return int(transfer["episode"]) in {int(item) for item in episodes if item}


async def refresh_index_and_subscription_for_transfer(transfer: dict, *, reason: str, db_path: str = DB_PATH) -> dict:
    index_refresh = None
    if db_path == DB_PATH:
        index_refresh = await refresh_jellyfin_library_index_if_stale(reason=reason, force=True, db_path=db_path)
    has_episode = await jellyfin_has_subscription_episode(transfer)
    if has_episode and db_path == DB_PATH:
        await refresh_subscription_lifecycle_for_ids({int(transfer["subscription_id"])}, get_active_proxy_config())
    elif db_path == DB_PATH:
        await refresh_subscription_lifecycle_for_ids({int(transfer["subscription_id"])}, get_active_proxy_config())
    return {
        "history_id": transfer.get("history_id"),
        "subscription_id": transfer.get("subscription_id"),
        "season": transfer.get("season"),
        "episode": transfer.get("episode"),
        "has_episode": has_episode,
        "jellyfin_index_refresh": index_refresh,
    }


def build_library_missing_payload(transfer: dict, attempts: list[dict] | None = None) -> dict:
    season = int(transfer["season"])
    episode = int(transfer["episode"])
    target = f"S{season:02d}E{episode:02d}"
    title = transfer.get("keyword") or transfer.get("title") or "订阅内容"
    return {
        "id": f"library-missing:{transfer['history_id']}",
        "title": f"{title} {target} 转存后未入库",
        "resource_url": transfer.get("link"),
        "_target_season": season,
        "_target_episode": episode,
        "_library_missing": {
            "history_id": transfer.get("history_id"),
            "fingerprint": transfer.get("fingerprint"),
            "target": target,
            "attempts": attempts or [],
        },
        "_review": {
            "type": "library_missing",
            "reason": POST_TRANSFER_LIBRARY_MISSING_REASON,
            "reason_label": POST_TRANSFER_LIBRARY_MISSING_LABEL,
            "evidence": {
                "history_id": transfer.get("history_id"),
                "fingerprint": transfer.get("fingerprint"),
                "target": target,
                "message": "订阅转存后的内容未入库，请检查 Jellyfin。",
                "attempts": attempts or [],
            },
            "risk_flags": ["转存成功后未在 Jellyfin 中确认到目标集数"],
        },
    }


async def queue_library_missing_review(transfer: dict, attempts: list[dict] | None = None, db_path: str = DB_PATH) -> dict:
    payload = build_library_missing_payload(transfer, attempts)
    result_id = payload["id"]
    title = payload["title"]
    link = transfer.get("link") or f"library-missing:{transfer['history_id']}"
    inserted = await upsert_library_missing_review(
        subscription_id=transfer.get("subscription_id"),
        result_id=result_id,
        title=title,
        link=link,
        match_reason="转存成功后未在 Jellyfin 中确认到目标集数",
        payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        db_path=db_path,
    )
    return {"inserted": inserted, "result_id": result_id, "link": link}


async def confirm_transfer_library_state(history_id: int, *, attempt: int, db_path: str = DB_PATH) -> dict:
    transfer = await load_successful_subscription_transfer(history_id, db_path)
    if not transfer:
        return {"history_id": history_id, "skipped": "not_successful_subscription_episode_transfer"}
    result = await refresh_index_and_subscription_for_transfer(
        transfer,
        reason=f"subscription_transfer_confirm_attempt_{attempt}",
        db_path=db_path,
    )
    attempt_payload = {
        "attempt": attempt,
        "checked_at": datetime.now(LOCAL_TZ).isoformat(),
        "has_episode": result["has_episode"],
    }
    if result["has_episode"]:
        return {**result, "queued_review": False}
    if attempt < 2 and db_path == DB_PATH:
        schedule_subscription_transfer_confirmation(history_id, attempt=2, delay_seconds=SECOND_CONFIRM_DELAY_SECONDS)
        return {**result, "queued_retry": True}
    review = await queue_library_missing_review(transfer, [attempt_payload], db_path)
    return {**result, "queued_review": True, "review": review}


async def resolve_library_missing_review(pending_id: int, db_path: str = DB_PATH) -> dict:
    payload_json = await load_pending_payload_json(pending_id, db_path=db_path)
    if not payload_json:
        return {"resolved": False, "error": "pending_not_found"}
    try:
        payload = json.loads(payload_json or "{}")
    except Exception:
        payload = {}
    review = payload.get("_review") if isinstance(payload, dict) else None
    if not isinstance(review, dict) or review.get("reason") != POST_TRANSFER_LIBRARY_MISSING_REASON:
        return {"resolved": False, "error": "not_library_missing_review"}
    history_id = (payload.get("_library_missing") or {}).get("history_id")
    if not history_id:
        return {"resolved": False, "error": "missing_history_id"}
    result = await confirm_transfer_library_state(int(history_id), attempt=3, db_path=db_path)
    if not result.get("has_episode"):
        return {"resolved": False, "error": "episode_not_found", **result}
    await update_pending_transfer_status(pending_id, PENDING_TRANSFER_STATUS_RESOLVED, db_path=db_path)
    return {"resolved": True, **result}


async def reject_library_missing_review(pending_id: int, db_path: str = DB_PATH) -> bool:
    updated = await update_pending_transfer_status(
        pending_id,
        PENDING_TRANSFER_STATUS_REJECTED,
        from_status=PENDING_TRANSFER_STATUS_PENDING,
        db_path=db_path,
    )
    return updated > 0


async def _run_confirmation_job(history_id: int, attempt: int) -> None:
    try:
        await confirm_transfer_library_state(history_id, attempt=attempt)
    except Exception as exc:
        log_event(
            "subscription.transfer_confirmation.job_failed",
            "warning",
            history_id=history_id,
            attempt=attempt,
            error_type=type(exc).__name__,
        )


async def _delayed_confirmation_job(history_id: int, attempt: int, delay_seconds: int) -> None:
    await asyncio.sleep(max(0, int(delay_seconds)))
    await _run_confirmation_job(history_id, attempt)


def schedule_subscription_transfer_confirmation(
    history_id: int,
    *,
    attempt: int = 1,
    delay_seconds: int = FIRST_CONFIRM_DELAY_SECONDS,
) -> bool:
    try:
        from scheduler_service import get_scheduler

        scheduler = get_scheduler()
        if not scheduler or not scheduler.running:
            try:
                asyncio.get_running_loop().create_task(_delayed_confirmation_job(int(history_id), int(attempt), int(delay_seconds)))
            except RuntimeError:
                return False
            return True
        run_date = datetime.now(LOCAL_TZ) + timedelta(seconds=delay_seconds)
        scheduler.add_job(
            _run_confirmation_job,
            "date",
            run_date=run_date,
            args=[int(history_id), int(attempt)],
            id=f"subscription_transfer_confirm:{int(history_id)}:{int(attempt)}",
            name=f"订阅转存入库确认 #{history_id}/{attempt}",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        return True
    except Exception as exc:
        log_event(
            "subscription.transfer_confirmation.schedule_failed",
            "warning",
            history_id=history_id,
            attempt=attempt,
            error_type=type(exc).__name__,
        )
        return False


async def schedule_confirmations_for_successful_history_ids(history_ids: list[int], db_path: str = DB_PATH) -> dict:
    scheduled = 0
    skipped = 0
    for history_id in history_ids:
        try:
            transfer = await load_successful_subscription_transfer(int(history_id), db_path)
        except Exception as exc:
            log_event(
                "subscription.transfer_confirmation.history_skipped",
                "warning",
                history_id=history_id,
                error_type=type(exc).__name__,
            )
            skipped += 1
            continue
        if not transfer:
            skipped += 1
            continue
        if db_path == DB_PATH and schedule_subscription_transfer_confirmation(int(history_id), attempt=1):
            scheduled += 1
        else:
            skipped += 1
    return {"scheduled": scheduled, "skipped": skipped}
