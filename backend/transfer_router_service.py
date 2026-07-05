# -*- coding: utf-8 -*-
import asyncio
import json

from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

from config import DB_PATH
from pending_transfer_repository import (
    list_pending_transfer_rows,
    load_pending_payload_json as load_pending_payload_json_from_repository,
    load_pending_transfer_for_approval,
    update_pending_transfer_status,
)
from pending_transfer_status import (
    PENDING_TRANSFER_STATUS_ALL,
    PENDING_TRANSFER_STATUS_APPROVED,
    PENDING_TRANSFER_STATUS_PENDING,
    PENDING_TRANSFER_STATUS_REJECTED,
)
from schemas import TransferPayload
from search_scoring_service import extract_quality_tags
from structured_logging import log_event
from subscription_transfer_confirmation_service import (
    POST_TRANSFER_LIBRARY_MISSING_REASON,
    reject_library_missing_review,
)
from task_service import complete_task, create_task, fail_task
from title_utils import extract_result_display_title, has_meaningful_title_text
from transfer_service import (
    ForwardTransferAlreadyExists,
    process_forward_link,
    record_download_history,
    reserve_download_history,
    sync_cms_transfer_result_with_retries,
)
from utils import link_with_password, safe_task_result_link, stable_hash


PENDING_REASON_LABELS = {
    "manual_review": "人工审核",
    "missing_year": "年份缺失",
    "weak_title_match": "标题证据不足",
    "ambiguous_episode": "集数不明确",
    "weak_evidence": "证据不足",
    "low_confidence": "低于自动阈值",
    "safe_auto": "可自动转存",
    POST_TRANSFER_LIBRARY_MISSING_REASON: "转存后未入库",
}


def extract_pending_review(payload: dict | None, row: tuple) -> dict:
    review = (payload or {}).get("_review") if isinstance(payload, dict) else None
    if isinstance(review, dict):
        return review

    confidence = float(row[6] or 0)
    auto_transfer = bool(row[15]) if len(row) > 15 and row[15] is not None else True
    min_confidence = float(row[16] or 0)
    if not auto_transfer:
        reason = "manual_review"
    elif confidence <= 0:
        reason = "weak_evidence"
    elif min_confidence and confidence < min_confidence:
        reason = "low_confidence"
    else:
        reason = "weak_evidence"
    return {
        "reason": reason,
        "reason_label": PENDING_REASON_LABELS.get(reason, "需要审核"),
        "evidence": {
            "confidence": confidence,
            "min_confidence": min_confidence,
            "match_reason": row[7],
        },
        "risk_flags": [PENDING_REASON_LABELS.get(reason, "需要审核")],
    }


def payload_text(payload: dict | None, fallback_title: str | None = None) -> str:
    if not isinstance(payload, dict):
        return fallback_title or ""
    return "\n".join([
        payload.get("title") or fallback_title or "",
        payload.get("description") or "",
        payload.get("raw_text") or "",
    ])


async def load_pending_payload_json(pending_id: int, *, db_path: str = DB_PATH) -> str | None:
    return await load_pending_payload_json_from_repository(pending_id, db_path=db_path)


async def transfer_resource_task(
    payload: TransferPayload,
    background_tasks: BackgroundTasks,
) -> dict:
    link = link_with_password(payload.url, payload.password)
    fingerprint = payload.result_id or stable_hash(link)
    title = payload.title.strip() if payload.title else None

    reserved, history_id = await reserve_download_history(payload.subscription_id, fingerprint, link, title)
    if not reserved:
        return {"status": "skipped", "message": "该资源已处理过", "history_id": history_id}

    task_result_base = {"fingerprint": fingerprint, "link": safe_task_result_link(link)}
    task_id = create_task(
        "transfer",
        title or "资源转存",
        message="转存任务准备中...",
        result=task_result_base,
    )

    def sync_transfer() -> None:
        try:
            result = _run_transfer_sync(
                link,
                process_forward_link_fn=process_forward_link,
                record_history_fn=lambda message: asyncio.run(
                    record_download_history(payload.subscription_id, fingerprint, link, "submitted", message, title)
                ),
                sync_result_fn=lambda: asyncio.run(sync_cms_transfer_result_with_retries(history_id)),
            )
            _complete_transfer_from_sync_result(task_id, task_result_base, result)
        except ForwardTransferAlreadyExists as exc:
            log_event("transfer.skipped", "info", error=str(exc), **task_result_base)
            try:
                asyncio.run(record_download_history(payload.subscription_id, fingerprint, link, "skipped", title=title))
                complete_task(task_id, "目标端已存在，已跳过", {**task_result_base, "status": "skipped"})
            except Exception as record_error:
                fail_task(task_id, "记录跳过状态失败", str(record_error))
                log_event("transfer.record_skipped_failed", "error", error=str(record_error), **task_result_base)
        except Exception as exc:
            log_event("transfer.failed", "error", error=str(exc), **task_result_base)
            try:
                asyncio.run(record_download_history(payload.subscription_id, fingerprint, link, "failed", title=title))
            except Exception as record_error:
                log_event("transfer.record_failed_failed", "error", error=str(record_error), **task_result_base)
            fail_task(task_id, "转存任务失败", str(exc))

    background_tasks.add_task(sync_transfer)
    return {"status": "submitted", "message": "转存任务已提交 CMS，等待最终结果", "fingerprint": fingerprint, "task_id": task_id}


def _run_transfer_sync(
    link: str,
    *,
    process_forward_link_fn,
    record_history_fn,
    sync_result_fn,
) -> dict:
    response_text = process_forward_link_fn(link)
    message = response_text or "CMS 已接收转存任务，等待 115 最终结果"
    record_history_fn(message)
    return sync_result_fn()


def _complete_transfer_from_sync_result(task_id: str, task_result_base: dict, result: dict) -> None:
    if result.get("updated") and result.get("status") != "failed":
        complete_task(task_id, "转存任务已完成", {**task_result_base, **result})
        return
    fail_task(task_id, result.get("message") or "CMS 没有更新同步结果", str(result))


async def get_pending_transfers_payload(
    *,
    status: str = PENDING_TRANSFER_STATUS_PENDING,
    subscription_id: int | None = None,
    reason: str | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    sort: str = "latest",
    limit: int = 100,
    db_path: str = DB_PATH,
) -> list[dict]:
    rows = await list_pending_transfer_rows(
        status=status,
        status_all=PENDING_TRANSFER_STATUS_ALL,
        subscription_id=subscription_id,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        sort=sort,
        limit=limit,
        db_path=db_path,
    )
    items = []
    for row in rows:
        payload = None
        if row[9]:
            try:
                payload = json.loads(row[9])
            except Exception:
                payload = None
        title = row[3]
        if not has_meaningful_title_text(title):
            title = extract_result_display_title(payload, row[12] or "无标题资源")
        review = extract_pending_review(payload, row)
        if reason and reason != "all" and review.get("reason") != reason:
            continue
        text = payload_text(payload, title)
        quality_tags = (payload or {}).get("quality_tags") if isinstance(payload, dict) else None
        if not quality_tags:
            quality_tags = extract_quality_tags(text)
        items.append({
            "id": row[0],
            "subscription_id": row[1],
            "subscription_keyword": row[12],
            "subscription_media_type": row[13],
            "subscription_year": row[14],
            "subscription_auto_transfer": bool(row[15]) if row[15] is not None else None,
            "subscription_min_confidence": row[16],
            "subscription_quality_filter": row[17],
            "result_id": row[2],
            "title": title,
            "link": row[4],
            "password": row[5],
            "confidence": row[6],
            "match_reason": row[7],
            "status": row[8],
            "payload": payload,
            "pending_reason": review.get("reason"),
            "pending_reason_label": review.get("reason_label") or PENDING_REASON_LABELS.get(review.get("reason"), "需要审核"),
            "review_evidence": review.get("evidence") or {},
            "risk_flags": review.get("risk_flags") or [],
            "review_type": review.get("type") or ("library_missing" if review.get("reason") == POST_TRANSFER_LIBRARY_MISSING_REASON else "transfer"),
            "library_missing": (payload or {}).get("_library_missing") if isinstance(payload, dict) else None,
            "target_season": (payload or {}).get("_target_season") if isinstance(payload, dict) else None,
            "target_episode": (payload or {}).get("_target_episode") if isinstance(payload, dict) else None,
            "source_label": (payload or {}).get("source_label") if isinstance(payload, dict) else None,
            "publish_date": (payload or {}).get("publish_date") if isinstance(payload, dict) else None,
            "quality_tags": quality_tags,
            "created_at": row[10],
            "updated_at": row[11],
        })
    if sort == "reason":
        items.sort(key=lambda item: ((item.get("pending_reason_label") or ""), -int(item.get("id") or 0)))
    return items


async def approve_pending_transfer_task(
    pending_id: int,
    background_tasks: BackgroundTasks,
    *,
    db_path: str = DB_PATH,
) -> dict:
    row = await load_pending_transfer_for_approval(pending_id, db_path=db_path)
    if not row:
        raise HTTPException(status_code=404, detail="待确认转存不存在或已处理")
    subscription_id, result_id, title, link, password = row
    payload_json = await load_pending_payload_json(pending_id, db_path=db_path)
    try:
        payload = json.loads(payload_json or "{}")
    except Exception:
        payload = {}
    review = payload.get("_review") if isinstance(payload, dict) else None
    if isinstance(review, dict) and review.get("reason") == POST_TRANSFER_LIBRARY_MISSING_REASON:
        raise HTTPException(status_code=400, detail="该记录是入库异常，请使用确认入库操作。")
    try:
        transfer_payload = TransferPayload(url=link, password=password, title=title, result_id=result_id, subscription_id=subscription_id, auto=False)
    except ValidationError:
        raise HTTPException(status_code=400, detail="待确认资源链接无效，仅允许转存 115 资源链接") from None
    response = await transfer_resource_task(transfer_payload, background_tasks)
    await update_pending_transfer_status(pending_id, PENDING_TRANSFER_STATUS_APPROVED, db_path=db_path)
    return response


async def reject_pending_transfer_task(pending_id: int, *, db_path: str = DB_PATH) -> dict:
    payload_json = await load_pending_payload_json(pending_id, db_path=db_path)
    if payload_json:
        try:
            payload = json.loads(payload_json or "{}")
        except Exception:
            payload = {}
        review = payload.get("_review") if isinstance(payload, dict) else None
        if isinstance(review, dict) and review.get("reason") == POST_TRANSFER_LIBRARY_MISSING_REASON:
            if not await reject_library_missing_review(pending_id, db_path):
                raise HTTPException(status_code=404, detail="待确认记录不存在或已处理")
            return {"status": "success", "message": "已标记为未入库"}

    updated = await update_pending_transfer_status(
        pending_id,
        PENDING_TRANSFER_STATUS_REJECTED,
        from_status=PENDING_TRANSFER_STATUS_PENDING,
        db_path=db_path,
    )
    if updated == 0:
        raise HTTPException(status_code=404, detail="待确认转存不存在或已处理")
    return {"status": "success", "message": "已拒绝"}
