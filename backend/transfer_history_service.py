# -*- coding: utf-8 -*-
import json

from config import DB_PATH
from pending_transfer_status import PENDING_TRANSFER_STATUS_PENDING
from title_utils import extract_result_display_title
from transfer_history_repository import (
    insert_pending_transfer_row,
    load_pending_transfer_identity_row,
    record_download_history_row,
    reserve_download_history_row,
)
from utils import stable_hash


async def record_download_history(
    subscription_id: int | None,
    fingerprint: str,
    link: str,
    status: str,
    message: str | None = None,
    title: str | None = None,
    db_path: str = DB_PATH,
) -> None:
    normalized_title = title.strip() if title else None
    await record_download_history_row(
        subscription_id=subscription_id,
        title=normalized_title,
        fingerprint=fingerprint,
        link=link,
        status=status,
        message=message,
        db_path=db_path,
    )


async def reserve_download_history(
    subscription_id: int | None,
    fingerprint: str,
    link: str,
    title: str | None = None,
    db_path: str = DB_PATH,
) -> tuple[bool, int | None]:
    normalized_title = title.strip() if title else None
    return await reserve_download_history_row(
        subscription_id=subscription_id,
        title=normalized_title,
        fingerprint=fingerprint,
        link=link,
        db_path=db_path,
    )


async def queue_pending_transfer(
    subscription_id: int | None,
    result: dict,
    db_path: str = DB_PATH,
) -> dict:
    link = result.get("resource_url") or result.get("url")
    if not link:
        return {"inserted": False, "reason": "missing_link", "existing_status": None}
    title = extract_result_display_title(result, "无标题资源")
    result_id = result.get("id") or stable_hash(link)
    inserted, pending_id = await insert_pending_transfer_row(
        subscription_id=subscription_id,
        result_id=result_id,
        title=title,
        link=link,
        password=result.get("password"),
        confidence=float(result.get("confidence") or 0),
        match_reason=result.get("match_reason"),
        payload_json=json.dumps(result, ensure_ascii=False),
        db_path=db_path,
    )
    if inserted:
        return {
            "inserted": True,
            "id": pending_id,
            "status": PENDING_TRANSFER_STATUS_PENDING,
            "result_id": result_id,
            "link": link,
        }

    existing = await load_pending_transfer_identity_row(
        subscription_id=subscription_id,
        result_id=result_id,
        link=link,
        db_path=db_path,
    )
    return {
        "inserted": False,
        "reason": "already_exists" if existing else "ignored",
        "existing_id": existing[0] if existing else None,
        "existing_status": existing[1] if existing else None,
        "result_id": result_id,
        "link": link,
    }
