# -*- coding: utf-8 -*-
import os

from config import DATA_DIR, DB_PATH, LOG_DIR, RUNTIME_DIR, SESSION_DIR, TMDB_API_KEY
from scheduler_service import get_scheduler
from structured_logging import get_recent_events, redact_url_password
from task_service import get_heavy_task_queue_state, list_tasks
from transfer_service import get_cms_base_url, get_cms_share_down_list_url


def check_cms() -> dict:
    base_url = get_cms_base_url()
    list_url = get_cms_share_down_list_url()
    configured = bool(base_url or list_url)
    if not configured:
        return {"status": "warning", "configured": False, "message": "CMS 未配置"}
    return {
        "status": "connected",
        "configured": True,
        "message": "CMS 已配置",
        "base_url": redact_url_password(base_url),
        "share_down_list_url": redact_url_password(list_url),
    }


def check_tmdb() -> dict:
    configured = bool(TMDB_API_KEY)
    if configured:
        return {"status": "connected", "configured": True, "message": "TMDB 已配置"}
    return {"status": "warning", "configured": False, "message": "TMDB 未配置，搜索增强能力受限"}


def _serialize_job(job) -> dict:
    return {
        "id": getattr(job, "id", None),
        "name": getattr(job, "name", None),
        "next_run_time": getattr(getattr(job, "next_run_time", None), "isoformat", lambda: None)(),
    }


def check_scheduler() -> dict:
    scheduler = get_scheduler()
    if not scheduler:
        return {"status": "warning", "running": False, "jobs": [], "message": "调度器未启动"}
    jobs = [_serialize_job(job) for job in scheduler.get_jobs()]
    status = "connected" if scheduler.running else "warning"
    return {
        "status": status,
        "running": bool(scheduler.running),
        "jobs": jobs,
        "job_count": len(jobs),
        "message": "调度器运行中" if scheduler.running else "调度器未运行",
    }


def check_runtime_paths() -> dict:
    paths = {
        "runtime_dir": RUNTIME_DIR,
        "data_dir": DATA_DIR,
        "session_dir": SESSION_DIR,
        "log_dir": LOG_DIR,
        "db_path": DB_PATH,
    }
    items = []
    missing = []
    for key, path in paths.items():
        exists = os.path.exists(path)
        writable_target = path if os.path.isdir(path) else os.path.dirname(path)
        writable = os.access(writable_target or ".", os.W_OK)
        item = {"key": key, "configured": bool(path), "exists": exists, "writable": writable}
        items.append(item)
        if not exists and key != "db_path":
            missing.append(key)
    status = "connected" if not missing and all(item["writable"] for item in items) else "warning"
    return {
        "status": status,
        "items": items,
        "message": "运行目录可访问" if status == "connected" else "部分运行路径不可用",
    }


def recent_failed_tasks() -> dict:
    payload = list_tasks(status="failed", page=1, limit=5)
    return {
        "status": "connected",
        "items": payload.get("items", []),
        "total": payload.get("total", 0),
        "message": "最近失败任务已加载",
    }


def task_queue_state() -> dict:
    state = get_heavy_task_queue_state()
    status = "warning" if state.get("shutting_down") else "connected"
    return {
        "status": status,
        "message": "任务队列正在关闭" if state.get("shutting_down") else "任务队列可接收任务",
        **state,
    }


def recent_events() -> dict:
    items = get_recent_events(limit=20)
    return {
        "status": "connected",
        "items": items,
        "total": len(items),
        "message": f"最近 {len(items)} 条结构化事件",
    }
