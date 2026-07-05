# -*- coding: utf-8 -*-
import time
import uuid
from collections.abc import Callable

from task_status import (
    ACTIVE_TASK_STATUSES,
    TASK_STATUS_CANCEL_REQUESTED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_QUEUED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
)


def cleanup_tasks(
    task_store: dict[str, dict],
    max_age_seconds: int,
    *,
    now_fn: Callable[[], float] = time.time,
) -> None:
    now = now_fn()
    expired = []
    for task_id, task in task_store.items():
        created_at = task.get("created_at", now)
        if task.get("status") not in {TASK_STATUS_QUEUED, TASK_STATUS_RUNNING} and now - created_at > max_age_seconds:
            expired.append(task_id)
    for task_id in expired:
        task_store.pop(task_id, None)


def get_mutable_task(
    task_id: str,
    task_store: dict[str, dict],
    *,
    db_path: str,
    load_task_fn: Callable[[str, str], dict | None],
) -> dict | None:
    task = task_store.get(task_id)
    if task:
        return task
    task = load_task_fn(task_id, db_path)
    if task:
        task_store[task_id] = task
    return task


def create_task(
    task_store: dict[str, dict],
    *,
    db_path: str,
    persist_task_fn: Callable[[dict, str], bool],
    log_event_fn: Callable[..., None],
    cleanup_tasks_fn: Callable[..., None] = cleanup_tasks,
    cleanup_max_age_seconds: int = 3600,
    task_type: str,
    title: str,
    total: int = 0,
    message: str = "任务准备中...",
    result: dict | None = None,
    now_fn: Callable[[], float] = time.time,
    id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    **extra,
) -> str:
    cleanup_tasks_fn(task_store, cleanup_max_age_seconds)
    task_id = f"{task_type}_{id_factory()}"
    now = now_fn()
    task_store[task_id] = {
        "task_id": task_id,
        "type": task_type,
        "title": title,
        "total": total,
        "current": 0,
        "status": TASK_STATUS_RUNNING,
        "message": message,
        "result": result or {},
        "error": None,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
        **extra,
    }
    persist_task_fn(task_store[task_id], db_path)
    log_event_fn("task.created", task_id=task_id, task_type=task_type, title=title, total=total)
    return task_id


def update_task(
    task_id: str,
    *,
    task_store: dict[str, dict],
    db_path: str,
    persist_task_fn: Callable[[dict, str], bool],
    load_task_fn: Callable[[str, str], dict | None],
    log_event_fn: Callable[..., None],
    current: int | None = None,
    total: int | None = None,
    message: str | None = None,
    result_patch: dict | None = None,
    now_fn: Callable[[], float] = time.time,
    **extra,
) -> None:
    task = get_mutable_task(task_id, task_store, db_path=db_path, load_task_fn=load_task_fn)
    if not task:
        return
    if current is not None:
        task["current"] = current
    if total is not None:
        task["total"] = total
    if message is not None:
        task["message"] = message
    if result_patch:
        task.setdefault("result", {}).update(result_patch)
    task.update(extra)
    task["updated_at"] = now_fn()
    persist_task_fn(task, db_path)
    log_event_fn(
        "task.updated",
        "debug",
        task_id=task_id,
        task_type=task.get("type"),
        current=task.get("current"),
        total=task.get("total"),
    )


def complete_task(
    task_id: str,
    *,
    task_store: dict[str, dict],
    db_path: str,
    persist_task_fn: Callable[[dict, str], bool],
    load_task_fn: Callable[[str, str], dict | None],
    log_event_fn: Callable[..., None],
    message: str | None = None,
    result: dict | None = None,
    now_fn: Callable[[], float] = time.time,
) -> None:
    task = get_mutable_task(task_id, task_store, db_path=db_path, load_task_fn=load_task_fn)
    if not task:
        return
    if message is not None:
        task["message"] = message
    if result is not None:
        task["result"] = result
    task["status"] = TASK_STATUS_COMPLETED
    task["error"] = None
    task["updated_at"] = now_fn()
    task["finished_at"] = task["updated_at"]
    persist_task_fn(task, db_path)
    log_event_fn("task.completed", task_id=task_id, task_type=task.get("type"), message=task.get("message"))


def request_cancel_task(
    task_id: str,
    *,
    task_store: dict[str, dict],
    db_path: str,
    persist_task_fn: Callable[[dict, str], bool],
    load_task_fn: Callable[[str, str], dict | None],
    log_event_fn: Callable[..., None],
    message: str = "正在停止任务...",
    now_fn: Callable[[], float] = time.time,
) -> dict | None:
    task = get_mutable_task(task_id, task_store, db_path=db_path, load_task_fn=load_task_fn)
    if not task:
        return None
    if task.get("status") not in ACTIVE_TASK_STATUSES:
        return task
    if task.get("status") == TASK_STATUS_QUEUED:
        task["status"] = TASK_STATUS_CANCELLED
        task["message"] = "排队任务已停止"
        task["cancel_requested"] = True
        task["error"] = None
        task["updated_at"] = now_fn()
        task["finished_at"] = task["updated_at"]
        persist_task_fn(task, db_path)
        log_event_fn("task.cancelled", task_id=task_id, task_type=task.get("type"), message=task["message"])
        return task
    task["status"] = TASK_STATUS_CANCEL_REQUESTED
    task["message"] = message
    task["cancel_requested"] = True
    task["updated_at"] = now_fn()
    persist_task_fn(task, db_path)
    log_event_fn("task.cancel_requested", task_id=task_id, task_type=task.get("type"))
    return task


def is_cancel_requested(
    task_id: str | None,
    task_store: dict[str, dict],
    *,
    db_path: str,
    load_task_fn: Callable[[str, str], dict | None],
) -> bool:
    if not task_id:
        return False
    task = get_mutable_task(task_id, task_store, db_path=db_path, load_task_fn=load_task_fn)
    if not task:
        return False
    return bool(task.get("cancel_requested")) or task.get("status") in {TASK_STATUS_CANCEL_REQUESTED, TASK_STATUS_CANCELLED}


def cancel_task(
    task_id: str,
    *,
    task_store: dict[str, dict],
    db_path: str,
    persist_task_fn: Callable[[dict, str], bool],
    load_task_fn: Callable[[str, str], dict | None],
    log_event_fn: Callable[..., None],
    message: str = "任务已停止",
    result: dict | None = None,
    now_fn: Callable[[], float] = time.time,
) -> None:
    task = get_mutable_task(task_id, task_store, db_path=db_path, load_task_fn=load_task_fn)
    if not task:
        return
    task["status"] = TASK_STATUS_CANCELLED
    task["message"] = message
    task["cancel_requested"] = True
    if result is not None:
        task["result"] = result
    task["error"] = None
    task["updated_at"] = now_fn()
    task["finished_at"] = task["updated_at"]
    persist_task_fn(task, db_path)
    log_event_fn("task.cancelled", task_id=task_id, task_type=task.get("type"), message=message)


def fail_task(
    task_id: str,
    *,
    task_store: dict[str, dict],
    db_path: str,
    persist_task_fn: Callable[[dict, str], bool],
    load_task_fn: Callable[[str, str], dict | None],
    log_event_fn: Callable[..., None],
    message: str,
    error: str | None = None,
    now_fn: Callable[[], float] = time.time,
) -> None:
    task = get_mutable_task(task_id, task_store, db_path=db_path, load_task_fn=load_task_fn)
    if not task:
        return
    task["status"] = TASK_STATUS_FAILED
    task["message"] = message
    task["error"] = error or message
    task["updated_at"] = now_fn()
    task["finished_at"] = task["updated_at"]
    persist_task_fn(task, db_path)
    log_event_fn("task.failed", "error", task_id=task_id, task_type=task.get("type"), message=message, error=task["error"])
