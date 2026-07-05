# -*- coding: utf-8 -*-
import asyncio
import os
import re
from urllib.parse import urlparse

import aiohttp

from config import (
    CMS_BASE_URL,
    CMS_SHARE_DOWN_LIST_URL,
    CMS_TRANSFER_POLL_PAGE_SIZE,
    CMS_TRANSFER_SYNC_RETRY_ATTEMPTS,
    CMS_TRANSFER_SYNC_RETRY_DELAY_SECONDS,
    DB_PATH,
)
from db import connect_db
from download_history_status import (
    DOWNLOAD_STATUS_FAILED,
    DOWNLOAD_STATUS_SKIPPED,
    DOWNLOAD_STATUS_SUBMITTED,
    DOWNLOAD_STATUS_SUCCESS,
)
from jellyfin_library_index_service import refresh_jellyfin_library_index_if_stale
from subscription_transfer_confirmation_service import schedule_confirmations_for_successful_history_ids
from transfer_link_service import extract_115_share_code, extract_115_share_password
from utils import is_safe_external_url


CMS_TRANSFER_NO_RESULT_MESSAGE = "CMS 没有更新同步结果"


def get_cms_base_url() -> str:
    if CMS_BASE_URL:
        return CMS_BASE_URL
    forward_url = os.getenv("FORWARD_URL", "")
    if not forward_url:
        return ""
    parsed = urlparse(forward_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def get_cms_share_down_list_url() -> str:
    if CMS_SHARE_DOWN_LIST_URL:
        return CMS_SHARE_DOWN_LIST_URL
    base_url = get_cms_base_url()
    return f"{base_url}/api/share_down/list" if base_url else ""


def map_cms_transfer_status(record: dict) -> tuple[str, str] | None:
    cms_status = record.get("status")
    remark = (record.get("remark") or "").strip()
    share_name = (record.get("share_name") or record.get("f_name") or "").strip()
    message_parts = ["CMS 转存记录"]
    if share_name:
        message_parts.append(f"文件: {share_name}")
    if remark:
        message_parts.append(f"备注: {remark}")
    message = "；".join(message_parts)

    if cms_status == 1:
        return DOWNLOAD_STATUS_SUCCESS, message
    if cms_status == 2:
        if re.search(r"已经转存过|已转存过|重复|无需重复|文件已接收|已接收", remark):
            return DOWNLOAD_STATUS_SKIPPED, message
        return DOWNLOAD_STATUS_FAILED, message
    return None


def build_cms_transfer_record_lookup(records: list[dict]) -> dict[str, dict]:
    latest_by_code: dict[str, dict] = {}
    latest_by_code_pwd: dict[tuple[str, str], dict] = {}
    for record in records:
        share_code = record.get("share_id")
        if not share_code:
            continue
        share_pwd = record.get("share_pwd") or ""
        latest_by_code.setdefault(share_code, record)
        if share_pwd:
            latest_by_code_pwd.setdefault((share_code, share_pwd), record)
    return {
        "by_code": latest_by_code,
        "by_code_pwd": latest_by_code_pwd,
    }


def find_cms_transfer_record_for_link(link: str, lookup: dict[str, dict]) -> dict | None:
    share_code = extract_115_share_code(link)
    if not share_code:
        return None
    share_pwd = extract_115_share_password(link) or ""
    by_code_pwd = lookup.get("by_code_pwd") or {}
    by_code = lookup.get("by_code") or {}
    return by_code_pwd.get((share_code, share_pwd)) or by_code.get(share_code)


async def fetch_cms_share_down_records(page_size: int | None = None) -> list[dict]:
    list_url = get_cms_share_down_list_url()
    if not list_url:
        raise RuntimeError("未配置 CMS 转存记录地址。")
    if not is_safe_external_url(list_url, {"http", "https"}):
        raise RuntimeError("CMS 转存记录地址无效。")

    params = {"page": 1, "page_size": page_size or CMS_TRANSFER_POLL_PAGE_SIZE}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(list_url, params=params) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


async def sync_cms_transfer_results(limit: int = 100, db_path: str = DB_PATH) -> dict:
    async with connect_db(db_path) as conn:
        async with conn.execute(
            """
            SELECT id, link
            FROM download_history
            WHERE status = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (DOWNLOAD_STATUS_SUBMITTED, limit),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return {"checked": 0, "updated": 0, "message": "没有待同步的已提交任务"}

    records = await fetch_cms_share_down_records(max(CMS_TRANSFER_POLL_PAGE_SIZE, len(rows)))
    lookup = build_cms_transfer_record_lookup(records)

    updated = 0
    status_counts: dict[str, int] = {}
    successful_history_ids: list[int] = []
    async with connect_db(db_path) as conn:
        for history_id, link in rows:
            if not extract_115_share_code(link):
                continue
            record = find_cms_transfer_record_for_link(link, lookup)
            if not record:
                continue
            mapped = map_cms_transfer_status(record)
            if not mapped:
                continue
            status, message = mapped
            await conn.execute(
                """
                UPDATE download_history
                SET status = ?,
                    callback_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
                """,
                (status, message, history_id, DOWNLOAD_STATUS_SUBMITTED),
            )
            updated += 1
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == DOWNLOAD_STATUS_SUCCESS:
                successful_history_ids.append(int(history_id))
        await conn.commit()

    index_refresh = None
    if status_counts.get(DOWNLOAD_STATUS_SUCCESS, 0) > 0 and db_path == DB_PATH:
        index_refresh = await refresh_jellyfin_library_index_if_stale(reason="cms_transfer_success")
        await schedule_confirmations_for_successful_history_ids(successful_history_ids, db_path)

    return {
        "checked": len(rows),
        "updated": updated,
        "cms_records": len(records),
        "status_counts": status_counts,
        "jellyfin_index_refresh": index_refresh,
    }


async def _load_submitted_transfer(
    history_id: int | None = None,
    *,
    fingerprint: str | None = None,
    db_path: str = DB_PATH,
) -> tuple[int, str] | None:
    if history_id is None and not fingerprint:
        return None
    if history_id is not None:
        query = "SELECT id, link FROM download_history WHERE id = ? AND status = ?"
        params = (history_id,)
    else:
        query = "SELECT id, link FROM download_history WHERE fingerprint = ? AND status = ?"
        params = (fingerprint,)
    params = (*params, DOWNLOAD_STATUS_SUBMITTED)
    async with connect_db(db_path) as conn:
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
    return (int(row[0]), row[1]) if row else None


async def _mark_transfer_sync_no_result(history_id: int, db_path: str = DB_PATH) -> int:
    async with connect_db(db_path) as conn:
        cursor = await conn.execute(
            """
            UPDATE download_history
            SET status = ?,
                callback_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = ?
            """,
            (DOWNLOAD_STATUS_FAILED, CMS_TRANSFER_NO_RESULT_MESSAGE, history_id, DOWNLOAD_STATUS_SUBMITTED),
        )
        await conn.commit()
        return cursor.rowcount


async def sync_cms_transfer_result_for_history(
    history_id: int | None = None,
    *,
    fingerprint: str | None = None,
    db_path: str = DB_PATH,
) -> dict:
    row = await _load_submitted_transfer(history_id, fingerprint=fingerprint, db_path=db_path)
    if not row:
        return {
            "checked": 0,
            "updated": 0,
            "history_id": history_id,
            "fingerprint": fingerprint,
            "message": "没有待同步的已提交任务",
        }

    resolved_history_id, link = row
    share_code = extract_115_share_code(link)
    if not share_code:
        updated = await _mark_transfer_sync_no_result(resolved_history_id, db_path)
        return {
            "checked": 1,
            "updated": updated,
            "history_id": resolved_history_id,
            "fingerprint": fingerprint,
            "status": DOWNLOAD_STATUS_FAILED,
            "message": CMS_TRANSFER_NO_RESULT_MESSAGE,
        }

    records = await fetch_cms_share_down_records(CMS_TRANSFER_POLL_PAGE_SIZE)
    lookup = build_cms_transfer_record_lookup(records)
    matched_record = find_cms_transfer_record_for_link(link, lookup)

    if not matched_record:
        return {
            "checked": 1,
            "updated": 0,
            "history_id": resolved_history_id,
            "fingerprint": fingerprint,
            "cms_records": len(records),
            "message": CMS_TRANSFER_NO_RESULT_MESSAGE,
        }

    mapped = map_cms_transfer_status(matched_record)
    if not mapped:
        return {
            "checked": 1,
            "updated": 0,
            "history_id": resolved_history_id,
            "fingerprint": fingerprint,
            "cms_records": len(records),
            "message": CMS_TRANSFER_NO_RESULT_MESSAGE,
        }

    status, message = mapped
    async with connect_db(db_path) as conn:
        cursor = await conn.execute(
            """
            UPDATE download_history
            SET status = ?,
                callback_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = ?
            """,
            (status, message, resolved_history_id, DOWNLOAD_STATUS_SUBMITTED),
        )
        await conn.commit()

    index_refresh = None
    if status == DOWNLOAD_STATUS_SUCCESS and cursor.rowcount > 0 and db_path == DB_PATH:
        index_refresh = await refresh_jellyfin_library_index_if_stale(reason="cms_transfer_success")
        await schedule_confirmations_for_successful_history_ids([resolved_history_id], db_path)

    return {
        "checked": 1,
        "updated": cursor.rowcount,
        "history_id": resolved_history_id,
        "fingerprint": fingerprint,
        "cms_records": len(records),
        "status": status,
        "message": message,
        "jellyfin_index_refresh": index_refresh,
    }


async def sync_cms_transfer_result_with_retries(
    history_id: int | None = None,
    *,
    fingerprint: str | None = None,
    attempts: int = CMS_TRANSFER_SYNC_RETRY_ATTEMPTS,
    delay_seconds: int = CMS_TRANSFER_SYNC_RETRY_DELAY_SECONDS,
    db_path: str = DB_PATH,
) -> dict:
    attempts = max(1, int(attempts or 1))
    delay_seconds = max(0, int(delay_seconds or 0))
    last_result: dict | None = None
    for attempt in range(1, attempts + 1):
        result = await sync_cms_transfer_result_for_history(history_id, fingerprint=fingerprint, db_path=db_path)
        result["attempt"] = attempt
        result["attempts"] = attempts
        last_result = result
        if result.get("updated"):
            return result
        if attempt < attempts and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    resolved = await _load_submitted_transfer(history_id, fingerprint=fingerprint, db_path=db_path)
    resolved_history_id = resolved[0] if resolved else history_id
    updated = await _mark_transfer_sync_no_result(resolved_history_id, db_path) if resolved_history_id is not None else 0
    return {
        **(last_result or {}),
        "checked": 1,
        "updated": updated,
        "history_id": resolved_history_id,
        "fingerprint": fingerprint,
        "status": DOWNLOAD_STATUS_FAILED,
        "message": CMS_TRANSFER_NO_RESULT_MESSAGE,
        "attempt": attempts,
        "attempts": attempts,
    }
