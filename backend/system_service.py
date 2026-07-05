# -*- coding: utf-8 -*-
import asyncio
import time
from typing import Awaitable, Callable

from config import DB_PATH
from cache_service import cleanup_expired_caches, get_cache_stats
from jellyfin_service import get_jellyfin_status_payload
from system_local_checks_service import (
    check_cms as _check_cms,
    check_runtime_paths as _check_runtime_paths,
    check_scheduler as _check_scheduler,
    check_tmdb as _check_tmdb,
    recent_events as _recent_events,
    recent_failed_tasks as _recent_failed_tasks,
    task_queue_state as _task_queue_state,
)
from system_diagnostics_service import (
    build_configuration_health as _build_configuration_health,
    build_diagnostics as _build_diagnostics,
)
from system_repository import check_database_connectivity
from startup_state_service import get_startup_check
from telegram_service import get_proxy_payload, get_telegram_status_payload


CHECK_TIMEOUT_SECONDS = 1.5


def _ok(payload: dict | None = None) -> dict:
    return {"status": "connected", **(payload or {})}


def _warning(payload: dict | None = None) -> dict:
    return {"status": "warning", **(payload or {})}


def _failed(message: str, *, error: str | None = None) -> dict:
    payload = {"status": "disconnected", "message": message}
    if error:
        payload["error"] = error
    return payload


async def _with_timeout(label: str, check: Callable[[], Awaitable[dict]]) -> dict:
    try:
        return await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return _failed(f"{label} 检查超时")
    except Exception as exc:
        return _failed(f"{label} 检查失败", error=str(exc))


async def _check_database() -> dict:
    payload = await check_database_connectivity(DB_PATH, timeout_seconds=CHECK_TIMEOUT_SECONDS)
    return _ok({"message": "数据库可访问", "path_configured": bool(DB_PATH), **payload})


async def _check_telegram() -> dict:
    startup_check = get_startup_check("telegram")
    payload = await get_telegram_status_payload()
    connected = bool(payload.get("is_connected"))
    authorized = bool(payload.get("is_authorized"))
    status = "connected" if connected and authorized else "warning"
    message = "Telegram 已连接并授权" if connected and authorized else "Telegram 未连接或未授权"
    if startup_check and startup_check.get("status") != "connected" and not connected:
        payload["startup"] = startup_check
        message = startup_check.get("message") or message
        if startup_check.get("error"):
            payload["error"] = startup_check["error"]
    return {**payload, "status": status, "message": payload.get("error") or message}


async def _check_proxy() -> dict:
    payload = await get_proxy_payload()
    system_mode = payload.get("system_mode") or "direct"
    configured = bool(payload.get("host") and payload.get("port"))
    return _ok({
        "message": "代理已启用" if system_mode == "proxy" else "当前直连",
        "system_mode": system_mode,
        "configured": configured,
        "mode": payload.get("mode"),
        "enabled": payload.get("enabled", False),
        "protocol": payload.get("protocol"),
        "host": payload.get("host"),
        "port": payload.get("port"),
    })


async def _check_jellyfin() -> dict:
    payload = await get_jellyfin_status_payload()
    if payload.get("connected"):
        status = "connected"
    elif payload.get("configured"):
        status = "warning"
    else:
        status = "warning"
    return {**payload, "status": status}


async def _check_cache() -> dict:
    payload = await get_cache_stats()
    status = "warning" if payload.get("expired", 0) > payload.get("active", 0) and payload.get("expired", 0) > 0 else "connected"
    return {
        "status": status,
        "message": f"缓存有效 {payload.get('active', 0)} 条，过期 {payload.get('expired', 0)} 条",
        **payload,
    }


async def cleanup_system_cache_payload(table: str | None = None) -> dict:
    return await cleanup_expired_caches(table)


async def get_system_status_payload() -> dict:
    database_check, telegram_check, proxy_check, jellyfin_check, cache_check = await asyncio.gather(
        _with_timeout("数据库", _check_database),
        _with_timeout("Telegram", _check_telegram),
        _with_timeout("代理", _check_proxy),
        _with_timeout("Jellyfin", _check_jellyfin),
        _with_timeout("缓存", _check_cache),
    )
    checks = {
        "database": database_check,
        "telegram": telegram_check,
        "proxy": proxy_check,
        "jellyfin": jellyfin_check,
        "cache": cache_check,
        "cms": _check_cms(),
        "tmdb": _check_tmdb(),
        "scheduler": _check_scheduler(),
        "runtime_paths": _check_runtime_paths(),
        "recent_failed_tasks": _recent_failed_tasks(),
        "task_queue": _task_queue_state(),
        "recent_events": _recent_events(),
    }
    checks["configuration"] = _build_configuration_health(checks)
    overall_status = "connected"
    if any(check.get("status") == "disconnected" for check in checks.values()):
        overall_status = "disconnected"
    elif any(check.get("status") == "warning" for check in checks.values()):
        overall_status = "warning"
    return {
        "status": overall_status,
        "generated_at": time.time(),
        "checks": checks,
        "diagnostics": _build_diagnostics(checks),
    }
