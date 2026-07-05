# -*- coding: utf-8 -*-
import os
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    SUBSCRIPTION_CHECK_HOUR,
    SUBSCRIPTION_CHECK_INTERVAL_SECONDS,
    SUBSCRIPTION_CHECK_MINUTE,
    SUBSCRIPTION_ENABLED,
)
from subscription_schedule_state_service import (
    SUBSCRIPTION_SCHEDULER_JOB_ID,
)
from subscription_service import daily_subscription_check
from structured_logging import log_event
from task_service import create_task, enqueue_heavy_task, run_task_with_status
from telegram_service import get_active_proxy_config
from utils import safe_error_detail


LOCAL_TZ = ZoneInfo(os.getenv("TZ", "Asia/Shanghai"))
_scheduler: AsyncIOScheduler | None = None


async def run_daily_subscription_check(subscription_id: int | None = None, task_id: str | None = None) -> None:
    if task_id:
        await daily_subscription_check(subscription_id, proxy_config=get_active_proxy_config(), task_id=task_id)
        return

    queued_task_id = create_task(
        "subscription_check",
        "订阅检查",
        message="定时订阅检查任务排队中...",
        status="queued",
        subscription_id=subscription_id,
    )

    async def run_check_task() -> None:
        await run_task_with_status(
            queued_task_id,
            lambda: daily_subscription_check(
                subscription_id,
                proxy_config=get_active_proxy_config(),
                task_id=queued_task_id,
            ),
            success_message="订阅检查任务已完成",
            failure_message="订阅检查任务失败",
            result_builder=lambda result: result if isinstance(result, dict) else {"subscription_id": subscription_id},
            exception_error=safe_error_detail("订阅检查任务失败"),
            log_event_name="scheduler.subscription_check_failed",
            log_fields=lambda exc: {"error_type": type(exc).__name__},
            log_exception=False,
        )

    enqueue_heavy_task(queued_task_id, run_check_task)


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


async def start_scheduler() -> None:
    global _scheduler
    if not SUBSCRIPTION_ENABLED:
        log_event("scheduler.subscription_disabled")
        return

    try:
        _scheduler = AsyncIOScheduler(timezone=LOCAL_TZ)
        if SUBSCRIPTION_ENABLED:
            if SUBSCRIPTION_CHECK_INTERVAL_SECONDS > 0:
                _scheduler.add_job(
                    run_daily_subscription_check,
                    "interval",
                    seconds=SUBSCRIPTION_CHECK_INTERVAL_SECONDS,
                    id=SUBSCRIPTION_SCHEDULER_JOB_ID,
                    name="订阅间隔检查任务",
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=3600,
                )
            else:
                _scheduler.add_job(
                    run_daily_subscription_check,
                    "cron",
                    hour=SUBSCRIPTION_CHECK_HOUR,
                    minute=SUBSCRIPTION_CHECK_MINUTE,
                    id=SUBSCRIPTION_SCHEDULER_JOB_ID,
                    name="每日订阅检查任务",
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=3600,
                )
        _scheduler.start()
        if SUBSCRIPTION_ENABLED:
            if SUBSCRIPTION_CHECK_INTERVAL_SECONDS > 0:
                log_event(
                    "scheduler.started",
                    mode="interval",
                    interval_seconds=SUBSCRIPTION_CHECK_INTERVAL_SECONDS,
                    timezone=LOCAL_TZ.key,
                )
            else:
                log_event(
                    "scheduler.started",
                    mode="daily",
                    hour=SUBSCRIPTION_CHECK_HOUR,
                    minute=SUBSCRIPTION_CHECK_MINUTE,
                    timezone=LOCAL_TZ.key,
                )
    except Exception as exc:
        log_event("scheduler.start_failed", "error", error_type=type(exc).__name__)


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        log_event("scheduler.stopped")
    _scheduler = None
