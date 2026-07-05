# -*- coding: utf-8 -*-
from fastapi import BackgroundTasks

from poster_match_service import match_posters_for_messages
from task_service import create_task, enqueue_heavy_task, run_task_with_status
from telegram_service import get_active_proxy_config


async def match_posters_task(background_tasks: BackgroundTasks) -> dict:
    task_id = create_task("poster_match", "批量海报匹配", message="海报匹配任务排队中...", status="queued")

    async def process_posters_background():
        await run_task_with_status(
            task_id,
            lambda: match_posters_for_messages(proxy_config=get_active_proxy_config(), task_id=task_id),
            success_message=lambda stats: f"海报匹配完成，更新 {stats.get('updated_messages', 0)} 条消息",
            failure_message="海报匹配任务失败",
            log_event_name="messages.poster_match_failed",
        )

    enqueue_heavy_task(task_id, process_posters_background)
    return {"message": "海报匹配任务已加入后台队列，请稍后查看结果。", "task_id": task_id, "status": "queued"}
