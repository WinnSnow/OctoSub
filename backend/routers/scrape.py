# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi import Query

from schemas import RetryRequest
from scrape_service import get_task_progress_payload, retry_missing_links_payload, retry_single_message
from task_retry_service import retry_task_payload
from task_service import get_task, list_failed_task_reasons, list_tasks, request_cancel_task
from task_status import CANCELLABLE_TASK_STATUSES, TASK_STATUS_CANCEL_REQUESTED, VISIBLE_TASK_STATUSES


router = APIRouter()


@router.post("/api/messages/retry")
async def retry_message(request: RetryRequest):
    await retry_single_message(request.channel_name, request.message_id)
    return {"status": "success", "message": "重试完成"}


@router.post("/api/channels/{channel_name}/retry_missing")
async def retry_missing_links(channel_name: str):
    return await retry_missing_links_payload(channel_name)


@router.get("/api/tasks")
async def get_tasks(
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
):
    if status and status not in VISIBLE_TASK_STATUSES:
        raise HTTPException(status_code=400, detail="任务状态无效")
    return list_tasks(status=status, task_type=task_type, page=page, limit=limit)


@router.get("/api/tasks/failure-stats")
async def get_task_failure_stats(limit: int = Query(default=10, ge=1, le=50)):
    return list_failed_task_reasons(limit=limit)


@router.get("/api/tasks/{task_id}")
async def get_task_progress(task_id: str):
    try:
        return await get_task_progress_payload(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="任务不存在") from None


@router.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: str, background_tasks: BackgroundTasks):
    return await retry_task_payload(task_id, background_tasks)


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_running_task(task_id: str):
    try:
        task = get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="任务不存在") from None
    if task.get("status") not in CANCELLABLE_TASK_STATUSES:
        raise HTTPException(status_code=400, detail="只有排队中或运行中的任务可以停止")
    request_cancel_task(task_id)
    next_task = get_task(task_id)
    return {"status": next_task.get("status") or TASK_STATUS_CANCEL_REQUESTED, "task_id": task_id, "task": next_task}
