# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Request, Response

from auth_service import create_auth_token, password_matches, verify_auth_token
from config import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_TTL_SECONDS, ADMIN_USERNAME
from schemas import AdminLoginRequest


router = APIRouter()


@router.get("/api/health")
async def health_check():
    return {"status": "ok"}


@router.post("/api/auth/login")
async def admin_login(request: AdminLoginRequest, response: Response):
    if request.username != ADMIN_USERNAME or not password_matches(request.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_auth_token(request.username)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=AUTH_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=AUTH_COOKIE_SECURE,
        path="/",
    )
    return {"status": "success", "user": {"username": request.username}}


@router.get("/api/auth/me")
async def auth_me(request: Request):
    payload = verify_auth_token(request.cookies.get(AUTH_COOKIE_NAME))
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")
    return {"user": {"username": payload["u"]}}


@router.post("/api/auth/logout")
async def admin_logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"status": "success"}
