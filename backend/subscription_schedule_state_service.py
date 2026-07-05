# -*- coding: utf-8 -*-
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, time as datetime_time, timedelta, timezone
from zoneinfo import ZoneInfo

from config import (
    DB_PATH,
    SUBSCRIPTION_CHECK_HOUR,
    SUBSCRIPTION_CHECK_INTERVAL_SECONDS,
    SUBSCRIPTION_CHECK_MINUTE,
    SUBSCRIPTION_ENABLED,
)
from subscription_repository import get_latest_active_subscription_checked_at_value
from structured_logging import log_event


LOCAL_TZ = ZoneInfo(os.getenv("TZ", "Asia/Shanghai"))
SUBSCRIPTION_SCHEDULER_JOB_ID = "daily_subscription_check"
LAST_SUBSCRIPTION_CHECK = {
    "started_at": None,
    "finished_at": None,
    "status": None,
    "message": None,
}


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def local_time_string(value: datetime | None = None) -> str:
    return (value or local_now()).strftime("%Y-%m-%d %H:%M:%S")


def today_subscription_run_at(now: datetime | None = None) -> datetime:
    current = now or local_now()
    return datetime.combine(
        current.date(),
        datetime_time(hour=SUBSCRIPTION_CHECK_HOUR, minute=SUBSCRIPTION_CHECK_MINUTE),
        tzinfo=LOCAL_TZ,
    )


def format_subscription_check_interval(seconds: int | None = None) -> str:
    value = int(seconds if seconds is not None else SUBSCRIPTION_CHECK_INTERVAL_SECONDS)
    if value <= 0:
        return f"每天 {SUBSCRIPTION_CHECK_HOUR:02d}:{SUBSCRIPTION_CHECK_MINUTE:02d}"
    if value % 86400 == 0:
        return f"每 {value // 86400} 天"
    if value % 3600 == 0:
        return f"每 {value // 3600} 小时"
    if value % 60 == 0:
        return f"每 {value // 60} 分钟"
    return f"每 {value} 秒"


def parse_db_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def db_datetime_to_local_iso(value: str | None) -> str | None:
    parsed = parse_db_datetime(value)
    return parsed.isoformat() if parsed else None


async def get_latest_subscription_checked_at() -> datetime | None:
    return parse_db_datetime(await get_latest_active_subscription_checked_at_value(db_path=DB_PATH))


async def should_run_subscription_catchup() -> tuple[bool, str, datetime | None, datetime]:
    if not SUBSCRIPTION_ENABLED:
        return False, "订阅系统未启用", None, today_subscription_run_at()
    now = local_now()
    if SUBSCRIPTION_CHECK_INTERVAL_SECONDS > 0:
        latest_checked_at = await get_latest_subscription_checked_at()
        if latest_checked_at:
            next_run_at = latest_checked_at + timedelta(seconds=SUBSCRIPTION_CHECK_INTERVAL_SECONDS)
            if now < next_run_at:
                return False, "订阅间隔检查尚未到达", latest_checked_at, next_run_at
            return True, "服务启动时发现订阅间隔检查已到期，开始补跑", latest_checked_at, next_run_at
        return True, "服务启动时未发现订阅检查记录，开始首次检查", None, now

    scheduled_at = today_subscription_run_at(now)
    if now < scheduled_at:
        return False, "今天的计划检查时间尚未到达", await get_latest_subscription_checked_at(), scheduled_at
    latest_checked_at = await get_latest_subscription_checked_at()
    if latest_checked_at and latest_checked_at >= scheduled_at:
        return False, "今天计划检查已执行", latest_checked_at, scheduled_at
    return True, "服务启动时发现今天计划检查未执行，开始补跑", latest_checked_at, scheduled_at


async def run_subscription_catchup_if_needed(
    check_fn: Callable[..., Awaitable[None]],
    proxy_config: dict | None = None,
) -> None:
    try:
        should_run, reason, latest_checked_at, scheduled_at = await should_run_subscription_catchup()
        log_event(
            "subscription.catchup.evaluated",
            should_run=should_run,
            reason=reason,
            latest_checked_at=latest_checked_at.isoformat() if latest_checked_at else None,
            scheduled_at=scheduled_at.isoformat(),
        )
        if should_run:
            await check_fn(proxy_config=proxy_config)
    except Exception as exc:
        log_event("subscription.catchup.failed", "warning", error_type=type(exc).__name__)


async def get_subscription_scheduler_status_payload(scheduler) -> dict:
    jobs = []
    if scheduler:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })
    should_run, catchup_reason, latest_checked_at, scheduled_at = await should_run_subscription_catchup()
    return {
        "enabled": bool(scheduler and scheduler.running),
        "jobs": jobs,
        "last_check": LAST_SUBSCRIPTION_CHECK,
        "check_mode": "interval" if SUBSCRIPTION_CHECK_INTERVAL_SECONDS > 0 else "daily",
        "check_interval_seconds": SUBSCRIPTION_CHECK_INTERVAL_SECONDS,
        "check_interval_label": format_subscription_check_interval(),
        "check_time": f"{SUBSCRIPTION_CHECK_HOUR:02d}:{SUBSCRIPTION_CHECK_MINUTE:02d}",
        "timezone": LOCAL_TZ.key,
        "server_time": local_now().isoformat(),
        "today_scheduled_at": scheduled_at.isoformat(),
        "latest_subscription_checked_at": latest_checked_at.isoformat() if latest_checked_at else None,
        "catchup_needed": should_run,
        "catchup_reason": catchup_reason,
    }
