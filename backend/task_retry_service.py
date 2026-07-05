# -*- coding: utf-8 -*-
from fastapi import BackgroundTasks, HTTPException

from poster_match_service import match_posters_for_messages
from subscription_crud_service import get_subscription_ids_payload
from subscription_lifecycle_service import refresh_subscription_lifecycle_for_ids
from subscription_service import daily_subscription_check
from task_service import create_task, enqueue_heavy_task, get_task, run_task_with_status
from task_status import FAILED_TASK_STATUSES, TASK_STATUS_QUEUED
from telegram_service import get_active_proxy_config
from transfer_service import sync_cms_transfer_results


RETRYABLE_TASK_TYPES = {
    "subscription_check",
    "subscription_refresh",
    "cms_sync",
    "poster_match",
}


def is_retryable_task(task: dict) -> bool:
    return task.get("status") in FAILED_TASK_STATUSES and task.get("type") in RETRYABLE_TASK_TYPES


async def retry_task_payload(task_id: str, background_tasks: BackgroundTasks) -> dict:
    try:
        source_task = get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="任务不存在") from None

    if source_task.get("status") not in FAILED_TASK_STATUSES:
        raise HTTPException(status_code=400, detail="只有失败任务可以重试")

    task_type = source_task.get("type")
    if task_type not in RETRYABLE_TASK_TYPES:
        raise HTTPException(status_code=400, detail="该任务类型暂不支持重试")

    subscription_id = source_task.get("subscription_id")
    retry_task_id = create_task(
        task_type,
        f"{source_task.get('title') or '任务'}（重试）",
        message="重试任务排队中...",
        status=TASK_STATUS_QUEUED,
        retry_of=task_id,
        subscription_id=subscription_id,
    )

    if task_type == "subscription_check":
        async def run_subscription_check_retry():
            await run_task_with_status(
                retry_task_id,
                lambda: daily_subscription_check(subscription_id, proxy_config=get_active_proxy_config(), task_id=retry_task_id),
                success_message="订阅检查重试完成",
                failure_message="订阅检查重试失败",
                result_builder={"subscription_id": subscription_id, "retry_of": task_id},
            )

        enqueue_heavy_task(retry_task_id, run_subscription_check_retry)

    elif task_type == "subscription_refresh":
        async def run_subscription_refresh_retry():
            async def refresh():
                subscription_ids = await get_subscription_ids_payload(subscription_id)
                await refresh_subscription_lifecycle_for_ids(subscription_ids, get_active_proxy_config())
                return {"subscription_ids": subscription_ids, "retry_of": task_id}

            await run_task_with_status(
                retry_task_id,
                refresh,
                success_message="订阅状态刷新重试完成",
                failure_message="订阅状态刷新重试失败",
            )

        enqueue_heavy_task(retry_task_id, run_subscription_refresh_retry)

    elif task_type == "cms_sync":
        async def run_cms_sync_retry():
            async def sync():
                result = await sync_cms_transfer_results()
                result["retry_of"] = task_id
                return result

            await run_task_with_status(
                retry_task_id,
                sync,
                success_message="CMS 转存同步重试完成",
                failure_message="CMS 转存同步重试失败",
            )

        enqueue_heavy_task(retry_task_id, run_cms_sync_retry)

    elif task_type == "poster_match":
        async def run_poster_match_retry():
            async def match():
                stats = await match_posters_for_messages(proxy_config=get_active_proxy_config(), task_id=retry_task_id)
                stats["retry_of"] = task_id
                return stats

            await run_task_with_status(
                retry_task_id,
                match,
                success_message=lambda stats: f"海报匹配重试完成，更新 {stats.get('updated_messages', 0)} 条消息",
                failure_message="海报匹配重试失败",
            )

        enqueue_heavy_task(retry_task_id, run_poster_match_retry)

    return {
        "message": "重试任务已加入后台队列",
        "task_id": retry_task_id,
        "retry_of": task_id,
        "type": task_type,
        "status": TASK_STATUS_QUEUED,
    }
