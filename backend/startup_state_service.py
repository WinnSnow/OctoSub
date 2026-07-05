# -*- coding: utf-8 -*-
import time


_STARTUP_CHECKS: dict[str, dict] = {}


def mark_startup_check(name: str, status: str, message: str, *, error: str | None = None) -> None:
    payload = {
        "status": status,
        "message": message,
        "updated_at": time.time(),
    }
    if error:
        payload["error"] = error
    _STARTUP_CHECKS[name] = payload


def get_startup_check(name: str) -> dict | None:
    payload = _STARTUP_CHECKS.get(name)
    return dict(payload) if payload else None


def clear_startup_checks() -> None:
    _STARTUP_CHECKS.clear()
