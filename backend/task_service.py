# -*- coding: utf-8 -*-
import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from copy import deepcopy
import inspect
import time

from config import DB_PATH
from structured_logging import log_event, redact_mapping
import task_lifecycle_service
import task_query_service
from task_repository import (
    delete_tasks_by_type,
    list_failed_task_reasons as list_persisted_failed_task_reasons,
    list_active_persisted_tasks,
    list_persisted_tasks,
    load_task,
    persist_task,
)
from task_status import (
    ACTIVE_TASK_STATUSES,
    FINISHED_TASK_STATUSES,
    TASK_STATUS_ALL,
    TASK_STATUS_CANCEL_REQUESTED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_FAILED,
    TASK_STATUS_QUEUED,
    TASK_STATUS_RUNNING,
)


TASK_PROGRESS: dict[str, dict] = {}
TASK_TTL_SECONDS = 3600
TASK_LIST_LIMIT_MAX = 200
TASK_FAILURE_STATS_LIMIT_MAX = 50
TASK_PROGRESS_PERSIST_MIN_INTERVAL_SECONDS = 2.0
STALE_RUNNING_TASK_SECONDS = 1800
STALE_PREPARING_TASK_SECONDS = 300
CANCEL_REQUEST_TIMEOUT_SECONDS = 120
KNOWN_TASK_TYPES = {
    "fetch",
    "retry",
    "retry_missing_links",
    "poster_match",
    "transfer",
    "cms_sync",
    "subscription_check",
    "subscription_refresh",
    "jellyfin_library_sync",
}
RETRY_TASK_TYPES = {"retry", "retry_missing_links"}
TASK_STALE_TIMEOUT_SECONDS = {
    "cms_sync": 600,
    "poster_match": 3600,
    "subscription_check": 3600,
    "subscription_refresh": 3600,
    "fetch": 7200,
    "retry": 1800,
    "retry_missing_links": 1800,
    "transfer": 1800,
    "jellyfin_library_sync": 3600,
}
UNKNOWN_TASK_STALE_TIMEOUT_SECONDS = 300
STALE_FAILURE_MESSAGE = "任务已失去后台执行状态"
STALE_FAILURE_ERROR = "任务超过允许时间无进度，后台执行状态已失效"
CANCEL_TIMEOUT_MESSAGE = "任务停止请求超时，已强制收尾"
UNKNOWN_TASK_MESSAGE = "未知任务类型，已终止"
UNKNOWN_TASK_ERROR = "unknown task type"
QUEUED_STALE_MESSAGE = "排队任务已失去后台执行状态"
QUEUED_STALE_ERROR = "任务排队超过 5 分钟，后台执行状态已失效"

HeavyTaskFactory = Callable[[], Awaitable[None]]
TaskStatusMessage = str | Callable[[object], str]
TaskStatusResult = dict | Callable[[object], dict]
TaskExceptionMessage = str | Callable[[Exception], str]
TaskExceptionLogFields = dict | Callable[[Exception], dict]
_HEAVY_TASK_QUEUE: deque[tuple[str, HeavyTaskFactory]] = deque()
_HEAVY_TASK_WORKER: asyncio.Task | None = None
_HEAVY_TASK_RUNNING_ID: str | None = None
_HEAVY_TASK_RUNNING_TASK: asyncio.Task | None = None
_HEAVY_TASK_LOCK: asyncio.Lock | None = None
_HEAVY_TASK_ACCEPTING = True
_TASK_LAST_PERSIST_STATE: dict[str, dict] = {}


def _record_persist_state(task: dict) -> None:
    _TASK_LAST_PERSIST_STATE[task["task_id"]] = {
        "persisted_at": time.time(),
        "status": task.get("status"),
        "current": int(task.get("current") or 0),
        "total": int(task.get("total") or 0),
    }


def _persist_task(task: dict) -> bool:
    ok = persist_task(task, DB_PATH)
    if ok:
        _record_persist_state(task)
    else:
        log_event(
            "task.persist_failed",
            "error",
            task_id=task.get("task_id"),
            task_type=task.get("type"),
            status=task.get("status"),
        )
    return ok


def _persist_task_throttled(task: dict, db_path: str) -> bool:
    task_id = task.get("task_id")
    if not task_id:
        return persist_task(task, db_path)
    status = task.get("status")
    last = _TASK_LAST_PERSIST_STATE.get(task_id)
    if status != TASK_STATUS_RUNNING or not last or last.get("status") != status:
        ok = persist_task(task, db_path)
        if ok:
            _record_persist_state(task)
        return ok
    now = time.time()
    if now - float(last.get("persisted_at") or 0) >= TASK_PROGRESS_PERSIST_MIN_INTERVAL_SECONDS:
        ok = persist_task(task, db_path)
        if ok:
            _record_persist_state(task)
        return ok
    current = int(task.get("current") or 0)
    total = int(task.get("total") or 0)
    last_current = int(last.get("current") or 0)
    last_total = int(last.get("total") or 0)
    if total and (total != last_total or int(current * 100 / total) > int(last_current * 100 / total)):
        ok = persist_task(task, db_path)
        if ok:
            _record_persist_state(task)
        return ok
    return True


def _load_task(task_id: str) -> dict | None:
    return load_task(task_id, DB_PATH)


def _get_mutable_task(task_id: str) -> dict | None:
    return task_lifecycle_service.get_mutable_task(
        task_id,
        TASK_PROGRESS,
        db_path=DB_PATH,
        load_task_fn=load_task,
    )


def _task_age_seconds(task: dict, now: float) -> float:
    updated_at = float(task.get("updated_at") or task.get("created_at") or 0)
    return now - updated_at


def _is_unstarted_task(task: dict) -> bool:
    message = task.get("message") or ""
    return int(task.get("current") or 0) == 0 and int(task.get("total") or 0) == 0 and "准备中" in message


def _stale_timeout_for_task(task: dict) -> int:
    return TASK_STALE_TIMEOUT_SECONDS.get(task.get("type"), UNKNOWN_TASK_STALE_TIMEOUT_SECONDS)


def _stale_reason_for_task(task: dict, now: float | None = None) -> tuple[str, str, str] | None:
    if not task or task.get("status") not in ACTIVE_TASK_STATUSES:
        return None
    now = now or time.time()
    age = _task_age_seconds(task, now)
    if age < 0:
        return None
    if task.get("status") == TASK_STATUS_QUEUED:
        if age > STALE_PREPARING_TASK_SECONDS:
            return TASK_STATUS_FAILED, QUEUED_STALE_MESSAGE, QUEUED_STALE_ERROR
        return None
    task_type = task.get("type")
    if task_type not in KNOWN_TASK_TYPES:
        if age > UNKNOWN_TASK_STALE_TIMEOUT_SECONDS:
            return TASK_STATUS_FAILED, UNKNOWN_TASK_MESSAGE, UNKNOWN_TASK_ERROR
        return None
    if task.get("status") == TASK_STATUS_CANCEL_REQUESTED:
        if age > CANCEL_REQUEST_TIMEOUT_SECONDS:
            return TASK_STATUS_CANCELLED, CANCEL_TIMEOUT_MESSAGE, "cancel request timeout"
        return None
    if _is_unstarted_task(task) and age > STALE_PREPARING_TASK_SECONDS:
        return TASK_STATUS_FAILED, STALE_FAILURE_MESSAGE, "任务准备超过 5 分钟，后台执行状态已失效"
    if age > _stale_timeout_for_task(task):
        timeout_minutes = max(1, int(_stale_timeout_for_task(task) / 60))
        return TASK_STATUS_FAILED, STALE_FAILURE_MESSAGE, f"任务超过 {timeout_minutes} 分钟无进度，后台执行状态已失效"
    return None


def _is_stale_running_task(task: dict, now: float | None = None) -> bool:
    return _stale_reason_for_task(task, now) is not None


def _mark_task_failed(task_id: str, task: dict, message: str, error: str) -> dict:
    fail_task(task_id, message, error)
    updated = _get_mutable_task(task_id)
    return updated or {
        **task,
        "status": TASK_STATUS_FAILED,
        "message": message,
        "error": error,
        "finished_at": time.time(),
    }


def _force_cancel_task(task_id: str, task: dict, message: str) -> dict:
    cancel_task(task_id, message, {**(task.get("result") or {}), "cancelled": True, "cancel_timeout": True})
    updated = _get_mutable_task(task_id)
    return updated or {
        **task,
        "status": TASK_STATUS_CANCELLED,
        "message": message,
        "error": None,
        "finished_at": time.time(),
        "cancel_requested": True,
    }


def _converge_active_task(task_id: str, task: dict, now: float | None = None) -> dict:
    reason = _stale_reason_for_task(task, now)
    if not reason:
        return task
    status, message, error = reason
    if status == TASK_STATUS_CANCELLED:
        return _force_cancel_task(task_id, task, message)
    return _mark_task_failed(task_id, task, message, error)


def is_known_task_type(task_type: str | None) -> bool:
    return task_type in KNOWN_TASK_TYPES


def cleanup_polluted_tasks() -> dict:
    deleted_example = delete_tasks_by_type("example", DB_PATH)
    return {"deleted_example": deleted_example}


def converge_active_tasks() -> dict:
    now = time.time()
    changed = 0
    failed = 0
    cancelled = 0
    active_tasks = list_active_persisted_tasks(DB_PATH)
    for task in active_tasks:
        task_id = task.get("task_id")
        if not task_id:
            continue
        before_status = task.get("status")
        updated = _converge_active_task(task_id, task, now)
        if updated.get("status") != before_status:
            changed += 1
            if updated.get("status") == TASK_STATUS_CANCELLED:
                cancelled += 1
            elif updated.get("status") == TASK_STATUS_FAILED:
                failed += 1
    return {"checked": len(active_tasks), "changed": changed, "failed": failed, "cancelled": cancelled}


def prepare_task_store() -> dict:
    start_heavy_task_queue()
    cleanup_result = cleanup_polluted_tasks()
    converge_result = converge_active_tasks()
    return {"cleanup": cleanup_result, "converged": converge_result}


def _mark_task_stale(task_id: str, task: dict) -> dict:
    return _converge_active_task(task_id, task)


def _redact_task_for_output(task: dict) -> dict:
    output = deepcopy(task)
    if "result" in output:
        output["result"] = redact_mapping(output.get("result") or {})
    if output.get("error"):
        output["error"] = redact_mapping(output["error"])
    return output


def cleanup_tasks(max_age_seconds: int = TASK_TTL_SECONDS) -> None:
    task_lifecycle_service.cleanup_tasks(TASK_PROGRESS, max_age_seconds)


def create_task(
    task_type: str,
    title: str,
    total: int = 0,
    message: str = "任务准备中...",
    result: dict | None = None,
    **extra,
) -> str:
    return task_lifecycle_service.create_task(
        TASK_PROGRESS,
        db_path=DB_PATH,
        persist_task_fn=lambda task, _db_path: _persist_task(task),
        log_event_fn=log_event,
        cleanup_max_age_seconds=TASK_TTL_SECONDS,
        task_type=task_type,
        title=title,
        total=total,
        message=message,
        result=result,
        **extra,
    )


def update_task(
    task_id: str,
    *,
    current: int | None = None,
    total: int | None = None,
    message: str | None = None,
    result_patch: dict | None = None,
    **extra,
) -> None:
    task_lifecycle_service.update_task(
        task_id,
        task_store=TASK_PROGRESS,
        db_path=DB_PATH,
        persist_task_fn=_persist_task_throttled,
        load_task_fn=load_task,
        log_event_fn=log_event,
        current=current,
        total=total,
        message=message,
        result_patch=result_patch,
        **extra,
    )


def complete_task(task_id: str, message: str | None = None, result: dict | None = None) -> None:
    task_lifecycle_service.complete_task(
        task_id,
        task_store=TASK_PROGRESS,
        db_path=DB_PATH,
        persist_task_fn=lambda task, _db_path: _persist_task(task),
        load_task_fn=load_task,
        log_event_fn=log_event,
        message=message,
        result=result,
    )


def request_cancel_task(task_id: str, message: str = "正在停止任务...") -> dict | None:
    task = task_lifecycle_service.request_cancel_task(
        task_id,
        task_store=TASK_PROGRESS,
        db_path=DB_PATH,
        persist_task_fn=lambda task, _db_path: _persist_task(task),
        load_task_fn=load_task,
        log_event_fn=log_event,
        message=message,
    )
    if not task:
        return None

    removed_from_queue = _remove_queued_heavy_task(task_id)
    if not removed_from_queue:
        _cancel_running_heavy_task(task_id)
    return task


def is_cancel_requested(task_id: str | None) -> bool:
    return task_lifecycle_service.is_cancel_requested(
        task_id,
        TASK_PROGRESS,
        db_path=DB_PATH,
        load_task_fn=load_task,
    )


def cancel_task(task_id: str, message: str = "任务已停止", result: dict | None = None) -> None:
    task_lifecycle_service.cancel_task(
        task_id,
        task_store=TASK_PROGRESS,
        db_path=DB_PATH,
        persist_task_fn=lambda task, _db_path: _persist_task(task),
        load_task_fn=load_task,
        log_event_fn=log_event,
        message=message,
        result=result,
    )


def fail_task(task_id: str, message: str, error: str | None = None) -> None:
    task_lifecycle_service.fail_task(
        task_id,
        task_store=TASK_PROGRESS,
        db_path=DB_PATH,
        persist_task_fn=lambda task, _db_path: _persist_task(task),
        load_task_fn=load_task,
        log_event_fn=log_event,
        message=message,
        error=error,
    )


async def _resolve_task_operation(operation: Awaitable | Callable[[], Awaitable | object]) -> object:
    value = operation() if callable(operation) else operation
    if inspect.isawaitable(value):
        return await value
    return value


def _resolve_task_message(message: TaskStatusMessage, result: object) -> str:
    return message(result) if callable(message) else message


def _resolve_task_result(result: object, result_builder: TaskStatusResult | None) -> dict | None:
    if result_builder is None:
        return result if isinstance(result, dict) else None
    return result_builder(result) if callable(result_builder) else result_builder


async def run_task_with_status(
    task_id: str,
    operation: Awaitable | Callable[[], Awaitable | object],
    *,
    success_message: TaskStatusMessage,
    failure_message: str,
    result_builder: TaskStatusResult | None = None,
    exception_error: TaskExceptionMessage | None = None,
    log_event_name: str | None = None,
    log_fields: TaskExceptionLogFields | None = None,
    log_exception: bool = True,
    complete_task_fn: Callable[[str, str | None, dict | None], None] = complete_task,
    fail_task_fn: Callable[[str, str, str | None], None] = fail_task,
    cancel_task_fn: Callable[[str, str, dict | None], None] = cancel_task,
) -> object:
    try:
        result = await _resolve_task_operation(operation)
        if isinstance(result, dict):
            if result.get("cancelled"):
                cancel_task_fn(task_id, "任务已停止", result)
                return result
            if result.get("error"):
                fail_task_fn(task_id, failure_message, str(result.get("error")))
                return result
        complete_task_fn(
            task_id,
            _resolve_task_message(success_message, result),
            _resolve_task_result(result, result_builder),
        )
        return result
    except Exception as exc:
        error = exception_error(exc) if callable(exception_error) else exception_error
        fail_task_fn(task_id, failure_message, error or str(exc))
        if log_event_name:
            fields = log_fields(exc) if callable(log_fields) else (log_fields or {})
            error_field = {"error": str(exc)} if log_exception else {}
            log_event(log_event_name, "error", **error_field, task_id=task_id, **fields)
        return None


def get_task(task_id: str) -> dict:
    task = _get_mutable_task(task_id)
    if not task:
        raise KeyError(task_id)
    task = _converge_active_task(task_id, task)
    return _redact_task_for_output(task)


def _get_heavy_task_lock() -> asyncio.Lock:
    global _HEAVY_TASK_LOCK
    if _HEAVY_TASK_LOCK is None:
        _HEAVY_TASK_LOCK = asyncio.Lock()
    return _HEAVY_TASK_LOCK


def start_heavy_task_queue() -> None:
    global _HEAVY_TASK_ACCEPTING
    _HEAVY_TASK_ACCEPTING = True


def _remove_queued_heavy_task(task_id: str) -> bool:
    if not _HEAVY_TASK_QUEUE:
        return False
    retained = [item for item in _HEAVY_TASK_QUEUE if item[0] != task_id]
    removed = len(retained) != len(_HEAVY_TASK_QUEUE)
    if removed:
        _HEAVY_TASK_QUEUE.clear()
        _HEAVY_TASK_QUEUE.extend(retained)
        log_event("task_queue.queued_task_removed", task_id=task_id)
    return removed


def _cancel_running_heavy_task(task_id: str) -> bool:
    running_task = _HEAVY_TASK_RUNNING_TASK
    if _HEAVY_TASK_RUNNING_ID != task_id or not running_task or running_task.done():
        return False
    running_task.cancel()
    log_event("task_queue.running_task_cancelled", task_id=task_id)
    return True


async def _heavy_task_worker() -> None:
    global _HEAVY_TASK_RUNNING_ID, _HEAVY_TASK_RUNNING_TASK, _HEAVY_TASK_WORKER
    while True:
        async with _get_heavy_task_lock():
            if not _HEAVY_TASK_QUEUE:
                _HEAVY_TASK_WORKER = None
                _HEAVY_TASK_RUNNING_ID = None
                return
            task_id, task_factory = _HEAVY_TASK_QUEUE.popleft()
            _HEAVY_TASK_RUNNING_ID = task_id

        try:
            task = _get_mutable_task(task_id)
            if not task:
                await task_factory()
                continue
            if task.get("status") in {TASK_STATUS_CANCEL_REQUESTED, TASK_STATUS_CANCELLED} or task.get("cancel_requested"):
                cancel_task(task_id, "排队任务已停止", {**(task.get("result") or {}), "cancelled": True})
                continue
            if task.get("status") == TASK_STATUS_QUEUED:
                update_task(task_id, status=TASK_STATUS_RUNNING, message=task.get("message") or "任务开始执行")
            _HEAVY_TASK_RUNNING_TASK = asyncio.create_task(task_factory())
            try:
                await _HEAVY_TASK_RUNNING_TASK
            except asyncio.CancelledError:
                current = _get_mutable_task(task_id)
                if current and current.get("status") not in FINISHED_TASK_STATUSES:
                    cancel_task(
                        task_id,
                        "任务已停止",
                        {**(current.get("result") or {}), "cancelled": True},
                    )
                if asyncio.current_task().cancelling():
                    raise
        except Exception as exc:
            try:
                current = _get_mutable_task(task_id)
                if current and current.get("status") not in FINISHED_TASK_STATUSES:
                    fail_task(task_id, "后台任务执行失败", str(exc))
            except Exception as mark_exc:
                log_event(
                    "task_queue.mark_failed_failed",
                    "error",
                    task_id=task_id,
                    task_type=(current or {}).get("type") if "current" in locals() else None,
                    error=str(mark_exc),
                    original_error=str(exc),
                )
        finally:
            async with _get_heavy_task_lock():
                if _HEAVY_TASK_RUNNING_ID == task_id:
                    _HEAVY_TASK_RUNNING_ID = None
                    _HEAVY_TASK_RUNNING_TASK = None


def enqueue_heavy_task(task_id: str, task_factory: HeavyTaskFactory) -> asyncio.Task:
    global _HEAVY_TASK_WORKER
    if not _HEAVY_TASK_ACCEPTING:
        fail_task(task_id, "任务队列正在关闭", "heavy task queue is shutting down")
        raise RuntimeError("heavy task queue is shutting down")
    task = _get_mutable_task(task_id)
    if task and task.get("status") != TASK_STATUS_QUEUED:
        update_task(task_id, status=TASK_STATUS_QUEUED, message=task.get("message") or "任务排队中...")
    _HEAVY_TASK_QUEUE.append((task_id, task_factory))
    if _HEAVY_TASK_WORKER is None or _HEAVY_TASK_WORKER.done():
        _HEAVY_TASK_WORKER = asyncio.create_task(_heavy_task_worker())
    return _HEAVY_TASK_WORKER


async def shutdown_heavy_task_queue() -> dict:
    global _HEAVY_TASK_ACCEPTING, _HEAVY_TASK_WORKER
    _HEAVY_TASK_ACCEPTING = False
    cancelled_task_ids = []
    async with _get_heavy_task_lock():
        while _HEAVY_TASK_QUEUE:
            task_id, _factory = _HEAVY_TASK_QUEUE.popleft()
            cancelled_task_ids.append(task_id)
    for task_id in cancelled_task_ids:
        task = _get_mutable_task(task_id)
        if task and task.get("status") not in FINISHED_TASK_STATUSES:
            cancel_task(task_id, "服务关闭，排队任务已取消", {**(task.get("result") or {}), "cancelled": True, "shutdown": True})
    if _HEAVY_TASK_WORKER and _HEAVY_TASK_WORKER.done():
        _HEAVY_TASK_WORKER = None
    if cancelled_task_ids:
        log_event("task_queue.shutdown_cancelled", cancelled_count=len(cancelled_task_ids), task_ids=cancelled_task_ids)
    return {
        "accepting": _HEAVY_TASK_ACCEPTING,
        "running_task_id": _HEAVY_TASK_RUNNING_ID,
        "cancelled_task_ids": cancelled_task_ids,
        "cancelled_count": len(cancelled_task_ids),
    }


def get_heavy_task_queue_state() -> dict:
    return {
        "accepting": _HEAVY_TASK_ACCEPTING,
        "shutting_down": not _HEAVY_TASK_ACCEPTING,
        "running_task_id": _HEAVY_TASK_RUNNING_ID,
        "queued_task_ids": [task_id for task_id, _factory in _HEAVY_TASK_QUEUE],
        "queued_count": len(_HEAVY_TASK_QUEUE),
    }


def list_tasks(
    *,
    status: str | None = None,
    task_type: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict:
    if task_type and task_type != TASK_STATUS_ALL and not is_known_task_type(task_type):
        return {"items": [], "total": 0, "page": max(1, page), "limit": max(1, min(limit, TASK_LIST_LIMIT_MAX))}
    if status and status != TASK_STATUS_ALL:
        converge_active_tasks()
    payload = task_query_service.list_tasks(
        TASK_PROGRESS,
        status=status,
        task_type=task_type,
        task_types=KNOWN_TASK_TYPES,
        page=page,
        limit=limit,
        max_limit=TASK_LIST_LIMIT_MAX,
        db_path=DB_PATH,
        list_persisted_tasks_fn=list_persisted_tasks,
    )
    next_items = []
    changed_count = 0
    for item in payload.get("items") or []:
        if item.get("type") not in KNOWN_TASK_TYPES:
            continue
        updated = _converge_active_task(item["task_id"], item)
        if updated.get("status") != item.get("status"):
            changed_count += 1
        if status and status != TASK_STATUS_ALL and updated.get("status") != status:
            continue
        next_items.append(_redact_task_for_output(updated))
    payload["items"] = next_items
    if changed_count:
        payload["total"] = len(next_items)
    return payload


def list_failed_task_reasons(limit: int = 10) -> dict:
    payload = task_query_service.list_failed_task_reasons(
        TASK_PROGRESS,
        limit=limit,
        max_limit=TASK_FAILURE_STATS_LIMIT_MAX,
        db_path=DB_PATH,
        list_persisted_failed_task_reasons_fn=list_persisted_failed_task_reasons,
    )
    for item in payload.get("items") or []:
        if item.get("reason"):
            item["reason"] = redact_mapping(item["reason"])
    return payload
