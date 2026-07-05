# -*- coding: utf-8 -*-
"""FastAPI application assembly."""

from contextlib import asynccontextmanager
import fcntl
import json
import os

from fastapi import FastAPI, Request, Response

from auth_policy import (
    EXTERNAL_CALLBACK_API_PATHS,
    PUBLIC_AUTH_API_PATHS,
    is_auth_exempt_api_path,
    is_protected_api_path,
)
from auth_service import verify_auth_token
from config import AUTH_COOKIE_NAME, BACKEND_LOCK_PATH, ensure_runtime_dirs, validate_runtime_configuration, warn_if_temporary_auth_secret
from db import init_db, prepare_startup_data
from jellyfin_service import ensure_jellyfin_client
from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.douban import router as douban_router
from routers.download_history import router as download_history_router
from routers.jellyfin import router as jellyfin_router
from routers.messages import router as messages_router
from routers.scrape import router as scrape_router
from routers.search import router as search_router
from routers.subscriptions import configure_subscription_router, router as subscriptions_router
from routers.system import router as system_router
from routers.telegram import router as telegram_router
from routers.transfer import router as transfer_router
from scheduler_service import get_scheduler, run_daily_subscription_check, start_scheduler, stop_scheduler
from startup_state_service import mark_startup_check
from structured_logging import log_event
from task_service import prepare_task_store, shutdown_heavy_task_queue
from telegram_service import detect_connection_mode, restart_client, shutdown_client


_runtime_lock_file = None


def acquire_runtime_lock() -> None:
    global _runtime_lock_file
    lock_path = BACKEND_LOCK_PATH
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    _runtime_lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_runtime_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError(
            "检测到另一个后端实例仍在运行。请先执行 ./stop.sh；"
            "如果是 root 进程残留，请使用 sudo kill <PID> 清理后再启动。"
        ) from exc
    _runtime_lock_file.write(str(os.getpid()))
    _runtime_lock_file.flush()


def release_runtime_lock() -> None:
    global _runtime_lock_file
    if _runtime_lock_file:
        fcntl.flock(_runtime_lock_file.fileno(), fcntl.LOCK_UN)
        _runtime_lock_file.close()
        _runtime_lock_file = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_configuration()
    warn_if_temporary_auth_secret()
    ensure_runtime_dirs()
    acquire_runtime_lock()
    await init_db()

    try:
        await detect_connection_mode()
        await restart_client()
        mark_startup_check("telegram", "connected", "Telegram 启动初始化已完成。")
    except Exception as exc:
        mark_startup_check("telegram", "warning", "Telegram 启动初始化失败，相关功能暂不可用。", error=str(exc))
        log_event("startup.telegram_failed", "warning", error=str(exc))

    await prepare_startup_data()

    try:
        task_cleanup = prepare_task_store()
        log_event("startup.task_store_prepared", cleanup=task_cleanup)
    except Exception as exc:
        log_event("startup.task_store_failed", "error", error=str(exc))

    try:
        jellyfin = await ensure_jellyfin_client()
        if jellyfin:
            connected = await jellyfin.test_connection()
            if connected:
                log_event("startup.jellyfin_connected", base_url=jellyfin.base_url)
            else:
                log_event("startup.jellyfin_connection_failed", "warning", base_url=jellyfin.base_url)
        else:
            log_event("startup.jellyfin_not_configured")
    except Exception as exc:
        log_event("startup.jellyfin_failed", "error", error=str(exc))

    await start_scheduler()

    yield

    log_event("startup.shutdown")
    await shutdown_heavy_task_queue()
    await stop_scheduler()
    await shutdown_client()
    release_runtime_lock()


async def require_admin_login(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if is_protected_api_path(path):
        payload = verify_auth_token(request.cookies.get(AUTH_COOKIE_NAME))
        if not payload:
            return Response(
                content=json.dumps({"detail": "未登录"}),
                status_code=401,
                media_type="application/json",
            )
        request.state.user = {"username": payload["u"], "role": "admin"}
    return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    configure_subscription_router(run_daily_subscription_check, get_scheduler)
    app.middleware("http")(require_admin_login)
    app.include_router(auth_router)
    app.include_router(telegram_router)
    app.include_router(scrape_router)
    app.include_router(search_router)
    app.include_router(douban_router)
    app.include_router(jellyfin_router)
    app.include_router(subscriptions_router)
    app.include_router(download_history_router)
    app.include_router(dashboard_router)
    app.include_router(messages_router)
    app.include_router(transfer_router)
    app.include_router(system_router)
    return app


app = create_app()

__all__ = [
    "EXTERNAL_CALLBACK_API_PATHS",
    "PUBLIC_AUTH_API_PATHS",
    "acquire_runtime_lock",
    "app",
    "create_app",
    "is_auth_exempt_api_path",
    "is_protected_api_path",
    "lifespan",
    "release_runtime_lock",
    "require_admin_login",
]
