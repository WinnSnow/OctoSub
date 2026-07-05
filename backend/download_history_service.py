# -*- coding: utf-8 -*-
import asyncio
import sqlite3

from fastapi import BackgroundTasks, HTTPException

from config import DB_PATH
from download_history_repository import (
    count_download_history_by_status,
    insert_download_history,
    list_download_history_rows,
    load_download_history_for_retry,
    reserve_failed_download_history_retry,
    update_download_history_status,
)
from download_history_status import (
    DOWNLOAD_HISTORY_STATUSES,
    DOWNLOAD_STATUS_ALL,
    DOWNLOAD_STATUS_FAILED,
    DOWNLOAD_STATUS_SKIPPED,
    DOWNLOAD_STATUS_SUBMITTED,
    DOWNLOAD_STATUS_SUCCESS,
)
from schemas import DownloadHistoryPayload
from structured_logging import log_event
from task_service import complete_task, create_task, enqueue_heavy_task, fail_task, run_task_with_status, update_task
from transfer_service import (
    ForwardTransferAlreadyExists,
    process_forward_link,
    sync_cms_transfer_result_with_retries,
    sync_cms_transfer_results,
)
from task_status import TASK_STATUS_QUEUED
from utils import classify_resource_url, safe_task_result_link


async def count_submitted_download_history(db_path: str = DB_PATH) -> int:
    return await count_download_history_by_status(DOWNLOAD_STATUS_SUBMITTED, db_path=db_path)


def normalize_download_history_status(status: str | None, *, allow_all: bool = False) -> str | None:
    if not status:
        return None
    status = status.strip().lower()
    if allow_all and status == DOWNLOAD_STATUS_ALL:
        return None
    if status not in DOWNLOAD_HISTORY_STATUSES:
        suffix = " 或 all" if allow_all else ""
        raise HTTPException(status_code=400, detail=f"状态只能是 success、failed、skipped、submitted{suffix}。")
    return status


async def get_download_history_payload(
    *,
    subscription_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 100,
    db_path: str = DB_PATH,
) -> dict:
    if not isinstance(subscription_id, int):
        subscription_id = None
    status = normalize_download_history_status(status, allow_all=True)
    total, status_rows, rows = await list_download_history_rows(
        subscription_id=subscription_id,
        status=status,
        page=page,
        limit=limit,
        db_path=db_path,
    )

    items = [
        {
            "id": row[0],
            "subscription_id": row[1],
            "title": row[2] or row[9],
            "fingerprint": row[3],
            "link": row[4],
            "status": row[5],
            "created_at": row[6],
            "callback_message": row[7],
            "updated_at": row[8],
        }
        for row in rows
    ]
    status_counts = {row[0]: row[1] for row in status_rows}
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "stats": {
            "total": total,
            DOWNLOAD_STATUS_SUBMITTED: status_counts.get(DOWNLOAD_STATUS_SUBMITTED, 0),
            DOWNLOAD_STATUS_SUCCESS: status_counts.get(DOWNLOAD_STATUS_SUCCESS, 0),
            DOWNLOAD_STATUS_FAILED: status_counts.get(DOWNLOAD_STATUS_FAILED, 0),
            DOWNLOAD_STATUS_SKIPPED: status_counts.get(DOWNLOAD_STATUS_SKIPPED, 0),
        },
    }


async def sync_download_history_from_cms_task(background_tasks: BackgroundTasks, *, db_path: str = DB_PATH) -> dict:
    submitted_count = await count_submitted_download_history(db_path)
    if submitted_count <= 0:
        return {
            "message": "没有待同步的转存任务",
            "checked": 0,
            "updated": 0,
            "task_id": None,
        }

    task_id = create_task("cms_sync", "CMS 转存同步", message="CMS 同步任务排队中...", status=TASK_STATUS_QUEUED)

    async def run_sync_task():
        update_task(task_id, total=submitted_count, message="正在查询 CMS 转存结果...")
        await run_task_with_status(
            task_id,
            sync_cms_transfer_results,
            success_message="CMS 转存同步完成",
            failure_message="CMS 转存同步失败",
            log_event_name="download_history.cms_sync_failed",
        )

    enqueue_heavy_task(task_id, run_sync_task)
    return {"message": "CMS 转存结果同步任务已加入后台队列", "task_id": task_id, "status": "queued"}


async def _update_download_history_status(
    history_id: int,
    status: str,
    message: str | None = None,
    *,
    db_path: str = DB_PATH,
) -> None:
    await update_download_history_status(history_id, status, message, db_path=db_path)


async def retry_download_history_transfer_task(
    history_id: int,
    background_tasks: BackgroundTasks,
    *,
    db_path: str = DB_PATH,
) -> dict:
    row = await load_download_history_for_retry(history_id, db_path=db_path)
    if not row:
        raise HTTPException(status_code=404, detail="下载历史不存在")
    if row[5] != DOWNLOAD_STATUS_FAILED:
        raise HTTPException(status_code=400, detail="只有失败记录可以重试")
    if classify_resource_url(row[4]) != "115":
        raise HTTPException(status_code=400, detail="仅允许重试 115 资源链接")
    reserved = await reserve_failed_download_history_retry(history_id, db_path=db_path)
    if reserved == 0:
        raise HTTPException(status_code=409, detail="该记录状态已变化，请刷新后重试")

    _, subscription_id, title, fingerprint, link, _ = row
    task_result_base = {"fingerprint": fingerprint, "link": safe_task_result_link(link), "history_id": history_id}
    task_id = create_task(
        "transfer",
        title or "资源转存重试",
        message="转存重试任务准备中...",
        result=task_result_base,
        history_id=history_id,
        subscription_id=subscription_id,
    )

    def sync_retry_transfer() -> None:
        try:
            result = _run_retry_transfer_sync(
                history_id,
                link,
                update_status_fn=lambda status, message: asyncio.run(
                    _update_download_history_status(history_id, status, message, db_path=db_path)
                ),
                process_forward_link_fn=process_forward_link,
                sync_result_fn=lambda: asyncio.run(sync_cms_transfer_result_with_retries(history_id)),
            )
            _complete_retry_transfer_from_sync_result(task_id, task_result_base, result)
        except ForwardTransferAlreadyExists as exc:
            asyncio.run(_update_download_history_status(history_id, DOWNLOAD_STATUS_SKIPPED, str(exc), db_path=db_path))
            complete_task(task_id, "目标端已存在，已跳过", {**task_result_base, "status": DOWNLOAD_STATUS_SKIPPED})
        except Exception as exc:
            asyncio.run(_update_download_history_status(history_id, DOWNLOAD_STATUS_FAILED, str(exc), db_path=db_path))
            log_event("download_history.retry_failed", "error", error=str(exc), **task_result_base)
            fail_task(task_id, "转存重试失败", str(exc))

    background_tasks.add_task(sync_retry_transfer)
    return {"message": "转存重试任务已启动", "task_id": task_id, "history_id": history_id}


def _run_retry_transfer_sync(
    history_id: int,
    link: str,
    *,
    update_status_fn,
    process_forward_link_fn,
    sync_result_fn,
) -> dict:
    response_text = process_forward_link_fn(link)
    message = response_text or "CMS 已接收转存重试任务，等待 115 最终结果"
    update_status_fn(DOWNLOAD_STATUS_SUBMITTED, message)
    return sync_result_fn()


def _complete_retry_transfer_from_sync_result(task_id: str, task_result_base: dict, result: dict) -> None:
    if result.get("updated") and result.get("status") != DOWNLOAD_STATUS_FAILED:
        complete_task(task_id, "转存重试已完成", {**task_result_base, **result})
        return
    fail_task(task_id, result.get("message") or "CMS 没有更新同步结果", str(result))


async def add_download_history_payload(payload: DownloadHistoryPayload, *, db_path: str = DB_PATH) -> dict:
    fingerprint = payload.fingerprint.strip()
    link = payload.link.strip()
    status = normalize_download_history_status(payload.status)
    if not fingerprint:
        raise HTTPException(status_code=400, detail="业务指纹不能为空。")
    if not link:
        raise HTTPException(status_code=400, detail="资源链接不能为空。")

    try:
        history_id = await insert_download_history(
            subscription_id=payload.subscription_id,
            title=payload.title,
            fingerprint=fingerprint,
            link=link,
            status=status,
            db_path=db_path,
        )
        return {
            "id": history_id,
            "subscription_id": payload.subscription_id,
            "title": payload.title,
            "fingerprint": fingerprint,
            "link": link,
            "status": status,
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="该资源指纹或链接已存在。") from None
