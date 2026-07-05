# -*- coding: utf-8 -*-
from collections.abc import Callable
import inspect

from fastapi import APIRouter, BackgroundTasks

from schemas import SubscriptionCheckRequest, SubscriptionPayload, SubscriptionStatusUpdate
from subscription_crud_service import (
    add_subscription_payload,
    delete_subscription_payload,
    get_subscription_ids_payload,
    get_subscriptions_payload,
    update_subscription_payload,
    update_subscription_status_payload,
)
from subscription_schedule_state_service import get_subscription_scheduler_status_payload
from subscription_lifecycle_service import refresh_subscription_lifecycle_for_ids
from task_service import create_task, enqueue_heavy_task, fail_task, run_task_with_status
from telegram_service import get_active_proxy_config


router = APIRouter()
_daily_check_task: Callable | None = None
_scheduler_getter: Callable | None = None


def configure_subscription_router(daily_check_task: Callable, scheduler_getter: Callable) -> None:
    global _daily_check_task, _scheduler_getter
    _daily_check_task = daily_check_task
    _scheduler_getter = scheduler_getter


async def _run_daily_check(subscription_id: int | None, task_id: str) -> None:
    if _daily_check_task is None:
        return
    signature = inspect.signature(_daily_check_task)
    accepts_task_id = "task_id" in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if accepts_task_id:
        return await _daily_check_task(subscription_id, task_id=task_id)
    return await _daily_check_task(subscription_id)


@router.get("/api/subscriptions")
async def get_subscriptions():
    return await get_subscriptions_payload(get_active_proxy_config())


@router.post("/api/subscriptions/refresh-lifecycle")
async def refresh_subscription_lifecycle(background_tasks: BackgroundTasks, request: SubscriptionCheckRequest | None = None):
    subscription_id = request.subscription_id if request else None
    task_id = create_task(
        "subscription_refresh",
        "订阅状态刷新",
        message="订阅状态刷新任务排队中...",
        status="queued",
        subscription_id=subscription_id,
    )

    async def run_refresh_task():
        async def refresh():
            subscription_ids = await get_subscription_ids_payload(subscription_id)
            await refresh_subscription_lifecycle_for_ids(subscription_ids, get_active_proxy_config())
            return {"subscription_ids": subscription_ids}

        await run_task_with_status(
            task_id,
            refresh,
            success_message="订阅状态刷新完成",
            failure_message="订阅状态刷新失败",
        )

    enqueue_heavy_task(task_id, run_refresh_task)
    return {"message": "订阅状态刷新任务已加入后台队列", "subscription_id": subscription_id, "task_id": task_id, "status": "queued"}


@router.post("/api/subscriptions/check")
async def manual_subscription_check(background_tasks: BackgroundTasks, request: SubscriptionCheckRequest | None = None):
    subscription_id = request.subscription_id if request else None
    task_id = create_task(
        "subscription_check",
        "订阅检查",
        message="订阅检查任务排队中...",
        status="queued",
        subscription_id=subscription_id,
    )
    if _daily_check_task is not None:
        async def run_check_task():
            await run_task_with_status(
                task_id,
                lambda: _run_daily_check(subscription_id, task_id),
                success_message="订阅检查任务已完成",
                failure_message="订阅检查任务失败",
                result_builder=lambda result: result if isinstance(result, dict) else {"subscription_id": subscription_id},
            )

        enqueue_heavy_task(task_id, run_check_task)
    else:
        fail_task(task_id, "订阅检查任务不可用", "daily check task is not configured")
    return {"message": "订阅检查任务已加入后台队列", "subscription_id": subscription_id, "task_id": task_id, "status": "queued"}


@router.get("/api/subscriptions/scheduler")
async def get_subscription_scheduler_status():
    scheduler = _scheduler_getter() if _scheduler_getter is not None else None
    return await get_subscription_scheduler_status_payload(scheduler)


@router.post("/api/subscriptions")
async def add_subscription(payload: SubscriptionPayload):
    return await add_subscription_payload(payload)


@router.put("/api/subscriptions/{subscription_id}")
async def update_subscription(subscription_id: int, payload: SubscriptionPayload):
    return await update_subscription_payload(subscription_id, payload)


@router.patch("/api/subscriptions/{subscription_id}/status")
async def update_subscription_status(subscription_id: int, payload: SubscriptionStatusUpdate):
    return await update_subscription_status_payload(subscription_id, payload)


@router.delete("/api/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: int):
    return await delete_subscription_payload(subscription_id)
