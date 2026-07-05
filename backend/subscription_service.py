# -*- coding: utf-8 -*-
from config import DB_PATH
from jellyfin_service import ensure_jellyfin_client
from jellyfin_library_index_service import refresh_jellyfin_library_index_if_stale
from structured_logging import log_event
from subscription_check_item_service import process_subscription_check_item
from subscription_check_repository import fetch_active_subscriptions
from subscription_schedule_state_service import LAST_SUBSCRIPTION_CHECK, local_time_string
from task_service import cancel_task, is_cancel_requested, update_task


async def daily_subscription_check(
    subscription_id: int | None = None,
    proxy_config: dict | None = None,
    task_id: str | None = None,
) -> dict:
    LAST_SUBSCRIPTION_CHECK.update({
        "started_at": local_time_string(),
        "finished_at": None,
        "status": "running",
        "message": "订阅检查运行中",
    })
    log_event("subscription.check.started", subscription_id=subscription_id, task_id=task_id)

    try:
        subscriptions = await fetch_active_subscriptions(subscription_id, DB_PATH)

        if not subscriptions:
            log_event("subscription.check.no_active", subscription_id=subscription_id, task_id=task_id)
            if task_id:
                update_task(task_id, current=0, total=0, message="没有活动的订阅规则")
            LAST_SUBSCRIPTION_CHECK.update({
                "finished_at": local_time_string(),
                "status": "completed",
                "message": "没有活动的订阅规则",
            })
            return {"cancelled": False, "processed": 0, "submitted": 0, "skipped": 0, "pending": 0}

        log_event("subscription.check.subscriptions_loaded", total=len(subscriptions), task_id=task_id)
        if task_id:
            update_task(task_id, current=0, total=len(subscriptions), message=f"找到 {len(subscriptions)} 个订阅规则")
        jellyfin = await ensure_jellyfin_client()

        total_processed = 0
        total_downloaded = 0
        total_skipped = 0
        total_pending = 0

        for index, subscription_row in enumerate(subscriptions, start=1):
            if task_id and is_cancel_requested(task_id):
                result = {
                    "cancelled": True,
                    "processed": total_processed,
                    "submitted": total_downloaded,
                    "skipped": total_skipped,
                    "pending": total_pending,
                    "current": index - 1,
                    "total": len(subscriptions),
                }
                cancel_task(task_id, "订阅检查已停止", result)
                LAST_SUBSCRIPTION_CHECK.update({
                    "finished_at": local_time_string(),
                    "status": "cancelled",
                    "message": "订阅检查已停止",
                })
                return result
            sub_id, keyword, _quality_filter, media_type, sub_tmdb_id, _sub_tmdb_type, sub_year, _auto_transfer, _min_confidence = subscription_row[:9]
            log_event(
                "subscription.check.item_started",
                subscription_id=sub_id,
                index=index,
                total=len(subscriptions),
                media_type=media_type,
                tmdb_id=sub_tmdb_id,
                year=sub_year,
            )
            if task_id:
                update_task(
                    task_id,
                    current=index - 1,
                    total=len(subscriptions),
                    message=f"正在检查订阅 {index}/{len(subscriptions)}：{keyword}",
                    result_patch={
                        "active_subscription_id": sub_id,
                        "processed": total_processed,
                        "submitted": total_downloaded,
                        "skipped": total_skipped,
                        "pending": total_pending,
                    },
                )

            counts = await process_subscription_check_item(
                subscription_row,
                jellyfin,
                proxy_config,
                DB_PATH,
                should_stop_fn=(lambda: is_cancel_requested(task_id)) if task_id else None,
            )
            total_processed += counts["processed"]
            total_downloaded += counts["submitted"]
            total_skipped += counts["skipped"]
            total_pending += counts["pending"]

            if task_id and is_cancel_requested(task_id):
                result = {
                    "cancelled": True,
                    "processed": total_processed,
                    "submitted": total_downloaded,
                    "skipped": total_skipped,
                    "pending": total_pending,
                    "current": index,
                    "total": len(subscriptions),
                }
                cancel_task(task_id, "订阅检查已停止", result)
                LAST_SUBSCRIPTION_CHECK.update({
                    "finished_at": local_time_string(),
                    "status": "cancelled",
                    "message": "订阅检查已停止",
                })
                return result

            if task_id:
                update_task(
                    task_id,
                    current=index,
                    total=len(subscriptions),
                    message=f"已完成订阅 {index}/{len(subscriptions)}：{keyword}",
                    result_patch={
                        "active_subscription_id": sub_id,
                        "processed": total_processed,
                        "submitted": total_downloaded,
                        "skipped": total_skipped,
                        "pending": total_pending,
                    },
                )

        log_event(
            "subscription.check.completed",
            processed=total_processed,
            submitted=total_downloaded,
            skipped=total_skipped,
            pending=total_pending,
            task_id=task_id,
        )
        try:
            index_refresh = await refresh_jellyfin_library_index_if_stale(reason="subscription_check_completed")
            if task_id:
                update_task(task_id, result_patch={"jellyfin_index_refresh": index_refresh})
        except Exception as refresh_error:
            log_event(
                "subscription.check.jellyfin_index_refresh_failed",
                "warning",
                error_type=type(refresh_error).__name__,
            )
        LAST_SUBSCRIPTION_CHECK.update({
            "finished_at": local_time_string(),
            "status": "completed",
            "message": f"处理 {total_processed} 条，提交 {total_downloaded} 条，跳过 {total_skipped} 条，待确认 {total_pending} 条",
        })
        return {
            "cancelled": False,
            "processed": total_processed,
            "submitted": total_downloaded,
            "skipped": total_skipped,
            "pending": total_pending,
        }

    except Exception as exc:
        log_event("subscription.check.failed", "error", error_type=type(exc).__name__, task_id=task_id)
        LAST_SUBSCRIPTION_CHECK.update({
            "finished_at": local_time_string(),
            "status": "failed",
            "message": str(exc),
        })
        if task_id:
            update_task(task_id, message=f"订阅检查失败: {exc}")
        return {"cancelled": False, "error": str(exc)}
