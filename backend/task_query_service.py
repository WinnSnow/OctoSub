# -*- coding: utf-8 -*-
from copy import deepcopy
from collections.abc import Callable

from task_status import FAILED_TASK_STATUSES, TASK_STATUS_ALL


def normalize_page_limit(page: int, limit: int, *, max_limit: int) -> tuple[int, int]:
    return max(1, page), max(1, min(limit, max_limit))


def filter_memory_tasks(
    task_store: dict[str, dict],
    *,
    status: str | None = None,
    task_type: str | None = None,
) -> list[dict]:
    tasks = list(task_store.values())
    if status and status != TASK_STATUS_ALL:
        tasks = [task for task in tasks if task.get("status") == status]
    if task_type and task_type != TASK_STATUS_ALL:
        tasks = [task for task in tasks if task.get("type") == task_type]
    tasks.sort(key=lambda task: (task.get("updated_at") or 0, task.get("created_at") or 0), reverse=True)
    return tasks


def list_tasks(
    task_store: dict[str, dict],
    *,
    status: str | None = None,
    task_type: str | None = None,
    task_types: set[str] | None = None,
    page: int = 1,
    limit: int = 50,
    max_limit: int = 200,
    db_path: str,
    list_persisted_tasks_fn: Callable[..., dict | None],
) -> dict:
    page, limit = normalize_page_limit(page, limit, max_limit=max_limit)
    payload = list_persisted_tasks_fn(
        status=status,
        task_type=task_type,
        task_types=task_types,
        page=page,
        limit=limit,
        db_path=db_path,
    )
    if payload is not None:
        return payload

    offset = (page - 1) * limit
    tasks = filter_memory_tasks(task_store, status=status, task_type=task_type)
    return {
        "items": deepcopy(tasks[offset:offset + limit]),
        "total": len(tasks),
        "page": page,
        "limit": limit,
    }


def group_memory_failed_task_reasons(task_store: dict[str, dict], *, limit: int) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    for task in task_store.values():
        if task.get("status") not in FAILED_TASK_STATUSES:
            continue
        key = (task.get("type") or "unknown", task.get("error") or task.get("message") or "未知错误")
        item = grouped.setdefault(key, {
            "type": key[0],
            "reason": key[1],
            "count": 0,
            "latest_updated_at": 0,
        })
        item["count"] += 1
        item["latest_updated_at"] = max(item["latest_updated_at"], task.get("updated_at") or 0)
    return sorted(grouped.values(), key=lambda item: (item["count"], item["latest_updated_at"]), reverse=True)[:limit]


def list_failed_task_reasons(
    task_store: dict[str, dict],
    *,
    limit: int = 10,
    max_limit: int = 50,
    db_path: str,
    list_persisted_failed_task_reasons_fn: Callable[[int, str], dict | None],
) -> dict:
    limit = max(1, min(limit, max_limit))
    payload = list_persisted_failed_task_reasons_fn(limit, db_path)
    if payload is not None:
        return payload
    return {"items": deepcopy(group_memory_failed_task_reasons(task_store, limit=limit)), "limit": limit}
