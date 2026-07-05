# -*- coding: utf-8 -*-
from __future__ import annotations

from config import DB_PATH
from dashboard_repository import load_dashboard_counts
from jellyfin_service import get_jellyfin_status_payload
from system_service import get_system_status_payload
from task_service import list_tasks


def _dashboard_system_checks(system_status: dict) -> dict:
    checks = system_status.get("checks") or {}
    wanted = ("database", "telegram", "proxy", "jellyfin", "cache", "tmdb", "scheduler", "configuration")
    result = {}
    for key in wanted:
        check = checks.get(key) or {}
        result[key] = {
            "status": check.get("status"),
            "message": check.get("message"),
        }
        if key == "jellyfin":
            result[key]["configured"] = bool(check.get("configured"))
            result[key]["connected"] = bool(check.get("connected"))
        if key == "cache":
            result[key]["active"] = check.get("active", 0)
            result[key]["expired"] = check.get("expired", 0)
        if key == "proxy":
            result[key]["system_mode"] = check.get("system_mode")
    return result


def _dashboard_jellyfin_check(payload: dict) -> dict:
    if payload.get("connected"):
        status = "connected"
    elif payload.get("configured"):
        status = "warning"
    else:
        status = "warning"
    return {
        "status": status,
        "message": payload.get("message"),
        "configured": bool(payload.get("configured")),
        "connected": bool(payload.get("connected")),
        "url": payload.get("url"),
    }


async def build_dashboard_summary(db_path: str = DB_PATH) -> dict:
    counts = await load_dashboard_counts(db_path)
    jellyfin_index = counts["jellyfin_index"]
    recent_tasks = list_tasks(page=1, limit=5)
    system_status = await get_system_status_payload()
    jellyfin_status = await get_jellyfin_status_payload()
    system_checks = _dashboard_system_checks(system_status)
    system_checks["jellyfin"] = _dashboard_jellyfin_check(jellyfin_status)
    return {
        "library": {
            "messages": counts["messages_total"],
            "links": counts["links_total"],
            "jellyfin_items": jellyfin_index["total"],
            "jellyfin_movies": jellyfin_index["movies"],
            "jellyfin_series": jellyfin_index["series"],
            "jellyfin_episodes": jellyfin_index["episodes"],
            "jellyfin_last_sync_at": jellyfin_index["last_sync_at"],
        },
        "subscriptions": {
            "total": counts["subscriptions_total"],
            "active": counts["subscriptions_active"],
        },
        "downloads": {
            "total": counts["history_total"],
            "success": counts["history_success"],
            "pending_transfers": counts["pending_transfers"],
        },
        "tasks": {
            "recent": recent_tasks.get("items", []),
            "total": recent_tasks.get("total", 0),
        },
        "system": {
            "status": system_status.get("status"),
            "message": system_status.get("message"),
            "checks": system_checks,
        },
        "admin": None,
    }
