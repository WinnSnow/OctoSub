# -*- coding: utf-8 -*-
"""Compatibility module for older imports.

Application assembly now lives in app.py. Keep these re-exports so scripts and
tests that still import legacy_main continue to work while callers migrate.
"""

from app import (
    EXTERNAL_CALLBACK_API_PATHS,
    PUBLIC_AUTH_API_PATHS,
    acquire_runtime_lock,
    app,
    create_app,
    is_auth_exempt_api_path,
    is_protected_api_path,
    lifespan,
    release_runtime_lock,
    require_admin_login,
)
from db import init_db, prepare_startup_data
from jellyfin_service import ensure_jellyfin_client
from scheduler_service import start_scheduler, stop_scheduler
from startup_state_service import mark_startup_check
from task_service import prepare_task_store
from telegram_service import detect_connection_mode, restart_client, shutdown_client


__all__ = [
    "EXTERNAL_CALLBACK_API_PATHS",
    "PUBLIC_AUTH_API_PATHS",
    "acquire_runtime_lock",
    "app",
    "create_app",
    "detect_connection_mode",
    "ensure_jellyfin_client",
    "init_db",
    "is_auth_exempt_api_path",
    "is_protected_api_path",
    "lifespan",
    "mark_startup_check",
    "prepare_startup_data",
    "prepare_task_store",
    "release_runtime_lock",
    "require_admin_login",
    "restart_client",
    "shutdown_client",
    "start_scheduler",
    "stop_scheduler",
]
