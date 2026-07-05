# -*- coding: utf-8 -*-
from collections.abc import Awaitable, Callable

from config import DB_PATH
from structured_logging import log_event
from telegram_proxy_config_service import get_proxy_config
from telegram_proxy_probe_service import check_google_connectivity


async def determine_active_proxy_config(
    *,
    db_path: str = DB_PATH,
    get_proxy_config_fn: Callable[[str], Awaitable[dict | None]] = get_proxy_config,
    check_connectivity_fn: Callable[[dict | None], Awaitable[bool]] = check_google_connectivity,
) -> dict | None:
    log_event("telegram.proxy.mode.detect_started")

    db_config = await get_proxy_config_fn(db_path)

    if not db_config or not db_config.get("enabled", True) or db_config.get("mode") == "direct":
        log_event("telegram.proxy.mode.selected", mode="direct", reason="disabled_or_direct")
        return None

    mode = db_config.get("mode", "auto")

    if mode == "manual":
        log_event("telegram.proxy.mode.selected", mode="manual", proxy_config=db_config)
        return db_config

    log_event("telegram.proxy.mode.auto_probe_started", proxy_config=db_config)
    if await check_connectivity_fn(None):
        log_event("telegram.proxy.mode.selected", mode="direct", reason="direct_probe_success")
        return None

    log_event("telegram.proxy.mode.direct_probe_failed")
    if await check_connectivity_fn(db_config):
        log_event("telegram.proxy.mode.selected", mode="auto_proxy", proxy_config=db_config)
        return db_config

    log_event("telegram.proxy.mode.selected", "warning", mode="auto_proxy_fallback", proxy_config=db_config)
    return db_config


def build_telethon_proxy(proxy_config: dict | None):
    if not proxy_config:
        log_event("telegram.proxy.telethon.direct")
        return None

    import python_socks

    proxy_type_map = {
        "http": python_socks.ProxyType.HTTP,
        "socks4": python_socks.ProxyType.SOCKS4,
        "socks5": python_socks.ProxyType.SOCKS5,
    }
    protocol = proxy_config["protocol"].lower()
    proxy_type = proxy_type_map.get(protocol)

    if not proxy_type:
        log_event("telegram.proxy.telethon.unsupported_protocol", "warning", protocol=proxy_config["protocol"])
        return None

    log_event("telegram.proxy.telethon.proxy", protocol=protocol, host=proxy_config["host"], port=proxy_config["port"])
    return (
        proxy_type,
        proxy_config["host"],
        proxy_config["port"],
        True,
        proxy_config.get("username"),
        proxy_config.get("password"),
    )
