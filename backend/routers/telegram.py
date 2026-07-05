# -*- coding: utf-8 -*-
from fastapi import APIRouter

from schemas import LoginRequest, ProxyConfig, ProxyStateUpdate
from telegram_service import (
    delete_proxy_payload,
    get_proxy_payload,
    get_telegram_status_payload,
    logout_payload,
    reset_session_payload,
    send_login_code_payload,
    set_proxy_payload,
    test_proxy_payload,
    update_proxy_state_payload,
    verify_login_code_payload,
    verify_login_password_payload,
)


router = APIRouter()


@router.get("/api/telegram/status")
async def get_telegram_status():
    return await get_telegram_status_payload()


@router.post("/api/telegram/login/send-code")
async def send_code(request: LoginRequest):
    return await send_login_code_payload(request)


@router.post("/api/telegram/login/verify-code")
async def verify_code(request: LoginRequest):
    return await verify_login_code_payload(request)


@router.post("/api/telegram/login/verify-password")
async def verify_password(request: LoginRequest):
    return await verify_login_password_payload(request)


@router.post("/api/telegram/logout")
async def logout():
    return await logout_payload()


@router.post("/api/telegram/reset-session")
async def reset_session():
    return await reset_session_payload()


@router.get("/api/proxy")
async def get_proxy():
    return await get_proxy_payload()


@router.post("/api/proxy")
async def set_proxy(config: ProxyConfig):
    return await set_proxy_payload(config)


@router.patch("/api/proxy/state")
async def update_proxy_state(state: ProxyStateUpdate):
    return await update_proxy_state_payload(state)


@router.delete("/api/proxy")
async def delete_proxy():
    return await delete_proxy_payload()


@router.post("/api/proxy/test")
async def test_proxy(config: ProxyConfig):
    return await test_proxy_payload(config)
