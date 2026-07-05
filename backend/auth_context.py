# -*- coding: utf-8 -*-
from fastapi import HTTPException, Request


def get_current_admin(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if user:
        return user
    raise HTTPException(status_code=401, detail="未登录")


def require_admin(request: Request) -> dict:
    return get_current_admin(request)
