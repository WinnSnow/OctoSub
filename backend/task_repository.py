# -*- coding: utf-8 -*-
import json
import sqlite3
import time

from config import DB_PATH
from structured_logging import log_event, redact_mapping


def json_dumps(value: dict | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str | None) -> dict:
    if not value:
        return {}
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def persisted_task_result(task: dict) -> dict:
    return redact_mapping(task.get("result") or {})


def persisted_task_error(task: dict):
    error = task.get("error")
    return redact_mapping(error) if error else error


def metadata_from_task(task: dict) -> dict:
    reserved = {
        "task_id", "type", "title", "total", "current", "status", "message",
        "result", "error", "created_at", "updated_at", "finished_at",
    }
    return {key: value for key, value in task.items() if key not in reserved}


def task_from_row(row) -> dict:
    task = {
        "task_id": row["task_id"],
        "type": row["type"],
        "title": row["title"],
        "total": row["total"] or 0,
        "current": row["current"] or 0,
        "status": row["status"],
        "message": row["message"],
        "result": json_loads(row["result_json"]),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "finished_at": row["finished_at"],
    }
    task.update(json_loads(row["metadata_json"]))
    return task


def connect_sync(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def persist_task(task: dict, db_path: str = DB_PATH, *, attempts: int = 3, retry_delay: float = 0.05) -> bool:
    last_error: sqlite3.Error | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            with connect_sync(db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO tasks
                        (task_id, type, title, total, current, status, message,
                         result_json, error, metadata_json, created_at, updated_at, finished_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task["task_id"],
                        task["type"],
                        task["title"],
                        int(task.get("total") or 0),
                        int(task.get("current") or 0),
                        task["status"],
                        task.get("message"),
                        json_dumps(persisted_task_result(task)),
                        persisted_task_error(task),
                        json_dumps(metadata_from_task(task)),
                        float(task.get("created_at") or time.time()),
                        float(task.get("updated_at") or time.time()),
                        task.get("finished_at"),
                    ),
                )
            return True
        except sqlite3.Error as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(retry_delay * attempt)
    log_event(
        "task_repository.persist_failed",
        "error",
        task_id=task.get("task_id"),
        task_type=task.get("type"),
        error=str(last_error),
    )
    return False


def load_task(task_id: str, db_path: str = DB_PATH) -> dict | None:
    try:
        with connect_sync(db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    except sqlite3.Error:
        return None
    return task_from_row(row) if row else None


def list_persisted_tasks(
    *,
    status: str | None = None,
    task_type: str | None = None,
    task_types: set[str] | None = None,
    page: int = 1,
    limit: int = 50,
    db_path: str = DB_PATH,
) -> dict | None:
    offset = (page - 1) * limit
    clauses = []
    params: list[object] = []
    if status and status != "all":
        clauses.append("status = ?")
        params.append(status)
    if task_type and task_type != "all":
        clauses.append("type = ?")
        params.append(task_type)
    elif task_types:
        placeholders = ",".join("?" for _ in task_types)
        clauses.append(f"type IN ({placeholders})")
        params.extend(sorted(task_types))
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    try:
        with connect_sync(db_path) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM tasks {where_sql}", params).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT *
                FROM tasks
                {where_sql}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
    except sqlite3.Error:
        return None

    return {
        "items": [task_from_row(row) for row in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


def list_active_persisted_tasks(db_path: str = DB_PATH) -> list[dict]:
    try:
        with connect_sync(db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM tasks
            WHERE status IN ('queued', 'running', 'cancel_requested')
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
    except sqlite3.Error:
        return []
    return [task_from_row(row) for row in rows]


def delete_tasks_by_type(task_type: str, db_path: str = DB_PATH) -> int:
    try:
        with connect_sync(db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE type = ?", (task_type,))
            return cursor.rowcount or 0
    except sqlite3.Error:
        return 0


def list_failed_task_reasons(limit: int = 10, db_path: str = DB_PATH) -> dict | None:
    try:
        with connect_sync(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    type,
                    COALESCE(NULLIF(error, ''), NULLIF(message, ''), '未知错误') AS reason,
                    COUNT(*) AS count,
                    MAX(updated_at) AS latest_updated_at
                FROM tasks
                WHERE status IN ('failed', 'partial_failed')
                GROUP BY type, reason
                ORDER BY count DESC, latest_updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except sqlite3.Error:
        return None

    return {
        "items": [{
            "type": row["type"],
            "reason": row["reason"],
            "count": row["count"],
            "latest_updated_at": row["latest_updated_at"],
        } for row in rows],
        "limit": limit,
    }
