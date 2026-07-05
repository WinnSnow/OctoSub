# -*- coding: utf-8 -*-

PUBLIC_AUTH_API_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/health",
}

EXTERNAL_CALLBACK_API_PATHS = {
    "/api/wecom/callback",
}


def is_auth_exempt_api_path(path: str) -> bool:
    return path in PUBLIC_AUTH_API_PATHS or path in EXTERNAL_CALLBACK_API_PATHS


def is_protected_api_path(path: str) -> bool:
    return path.startswith("/api/") and not is_auth_exempt_api_path(path)
