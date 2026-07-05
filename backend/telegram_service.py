# -*- coding: utf-8 -*-
import asyncio
import os

import telethon
from fastapi import HTTPException
from telethon import TelegramClient

from config import API_HASH, API_ID, DB_PATH, RUNTIME_DIR, SESSION_DIR, SESSION_NAME
from schemas import LoginRequest, ProxyConfig, ProxyStateUpdate
from structured_logging import log_event
from telegram_proxy_service import (
    build_telethon_proxy as _build_telethon_proxy,
    check_google_connectivity as _check_google_connectivity,
    delete_proxy_payload as _delete_proxy_payload,
    detect_connection_mode as _detect_connection_mode,
    get_active_proxy_config as _get_active_proxy_config,
    get_proxy_config as _get_proxy_config,
    get_proxy_payload as _get_proxy_payload,
    set_proxy_payload as _set_proxy_payload,
    test_proxy_payload as _test_proxy_payload,
    update_proxy_state_payload as _update_proxy_state_payload,
)
from utils import safe_error_detail


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

client = TelegramClient(SESSION_NAME, API_ID, API_HASH) if API_ID and API_HASH else None
client_lock = asyncio.Lock()


def _truncate_file(path: str) -> None:
    with open(path, "wb") as file:
        file.write(b"")


def get_active_proxy_config() -> dict | None:
    return _get_active_proxy_config()


def get_telegram_client():
    return client


async def get_proxy_config() -> dict | None:
    return await _get_proxy_config(DB_PATH)


async def check_google_connectivity(proxy_config: dict | None = None) -> bool:
    return await _check_google_connectivity(proxy_config)


async def detect_connection_mode() -> None:
    return await _detect_connection_mode(db_path=DB_PATH)


async def restart_client() -> None:
    global client
    async with client_lock:
        if not API_ID or not API_HASH:
            log_event("telegram.client.unconfigured", "warning")
            client = None
            return

        log_event("telegram.client.restart_requested")
        if client and client.is_connected():
            await client.disconnect()

        client = TelegramClient(SESSION_NAME, API_ID, API_HASH, proxy=_build_telethon_proxy(get_active_proxy_config()))

        try:
            await client.connect()
            log_event("telegram.client.connected")
        except Exception as exc:
            log_event("telegram.client.connect_failed", "warning", error_type=type(exc).__name__)


async def shutdown_client() -> None:
    async with client_lock:
        if client and client.is_connected():
            await client.disconnect()
            log_event("telegram.client.disconnected")


async def get_telegram_status_payload() -> dict:
    if not client:
        return {"is_connected": False, "is_authorized": False}

    try:
        if not client.is_connected():
            try:
                await client.connect()
            except Exception:
                pass

        is_connected = client.is_connected()
        is_authorized = False
        user = None

        if is_connected:
            is_authorized = await client.is_user_authorized()
            if is_authorized:
                me = await client.get_me()
                user = f"{me.first_name} {me.last_name or ''} (@{me.username})" if me else "Unknown"

        return {
            "is_connected": is_connected,
            "is_authorized": is_authorized,
            "user": user,
        }
    except Exception as exc:
        log_event("telegram.status.failed", "warning", error_type=type(exc).__name__)
        return {"is_connected": False, "is_authorized": False, "error": safe_error_detail("Telegram 状态获取失败")}


async def send_login_code_payload(request: LoginRequest) -> dict:
    if not API_ID or not API_HASH or not client:
        raise HTTPException(status_code=503, detail="Telegram API_ID/API_HASH 未配置")
    if not client.is_connected():
        await client.connect()

    try:
        result = await client.send_code_request(request.phone)
        return {"status": "success", "phone_code_hash": result.phone_code_hash}
    except Exception as exc:
        log_event("telegram.login_code.send_failed", "warning", error_type=type(exc).__name__)
        raise HTTPException(status_code=400, detail=safe_error_detail("Telegram 操作失败")) from exc


async def verify_login_code_payload(request: LoginRequest) -> dict:
    if not API_ID or not API_HASH or not client:
        raise HTTPException(status_code=503, detail="Telegram API_ID/API_HASH 未配置")
    if not client.is_connected():
        await client.connect()

    try:
        await client.sign_in(request.phone, request.code, phone_code_hash=request.phone_code_hash)
        return {"status": "success"}
    except telethon.errors.SessionPasswordNeededError:
        return {"status": "password_needed"}
    except Exception as exc:
        log_event("telegram.login_code.verify_failed", "warning", error_type=type(exc).__name__)
        raise HTTPException(status_code=400, detail=safe_error_detail("Telegram 操作失败")) from exc


async def verify_login_password_payload(request: LoginRequest) -> dict:
    if not API_ID or not API_HASH or not client:
        raise HTTPException(status_code=503, detail="Telegram API_ID/API_HASH 未配置")
    if not client.is_connected():
        await client.connect()

    try:
        await client.sign_in(password=request.password)
        return {"status": "success"}
    except Exception as exc:
        log_event("telegram.login_password.verify_failed", "warning", error_type=type(exc).__name__)
        raise HTTPException(status_code=400, detail=safe_error_detail("Telegram 操作失败")) from exc


async def logout_payload() -> dict:
    try:
        if client and client.is_connected():
            await client.log_out()
            await restart_client()
            return {"status": "success"}
        return {"status": "not_connected"}
    except Exception as exc:
        log_event("telegram.logout.failed", "warning", error_type=type(exc).__name__)
        raise HTTPException(status_code=400, detail=safe_error_detail("Telegram 操作失败")) from exc


async def reset_session_payload() -> dict:
    try:
        if client:
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                pass

        session_file = SESSION_NAME if SESSION_NAME.endswith(".session") else f"{SESSION_NAME}.session"
        session_path = os.path.abspath(session_file)
        allowed_session_roots = [
            os.path.abspath(BASE_DIR),
            os.path.abspath(SESSION_DIR),
            os.path.abspath(os.path.join(RUNTIME_DIR, "sessions")),
        ]
        if not any(session_path == root or session_path.startswith(root + os.sep) for root in allowed_session_roots):
            raise RuntimeError("会话文件路径必须位于后端目录或 runtime/sessions 内。")

        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                log_event("telegram.session.removed")
            except OSError as exc:
                if exc.errno == 16:
                    await asyncio.to_thread(_truncate_file, session_path)
                    log_event("telegram.session.truncated", reason="busy_mount")
                else:
                    raise exc

        for ext in ["-journal", "-wal", "-shm"]:
            if os.path.exists(session_path + ext):
                try:
                    os.remove(session_path + ext)
                except Exception:
                    pass

        await restart_client()
        return {"status": "success", "message": "会话已重置，请重新登录"}
    except Exception as exc:
        log_event("telegram.session.reset_failed", "warning", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail=safe_error_detail("重置会话失败")) from exc


async def get_proxy_payload() -> dict:
    return await _get_proxy_payload(db_path=DB_PATH)


async def set_proxy_payload(config: ProxyConfig) -> dict:
    return await _set_proxy_payload(config, restart_client_fn=restart_client, db_path=DB_PATH)


async def update_proxy_state_payload(state: ProxyStateUpdate) -> dict:
    return await _update_proxy_state_payload(state, restart_client_fn=restart_client, db_path=DB_PATH)


async def delete_proxy_payload() -> dict:
    return await _delete_proxy_payload(restart_client_fn=restart_client, db_path=DB_PATH)


async def test_proxy_payload(config: ProxyConfig) -> dict:
    return await _test_proxy_payload(config)
