# -*- coding: utf-8 -*-
from collections.abc import Awaitable, Callable

from config import DB_PATH
from schemas import ProxyConfig, ProxyStateUpdate
from search_aggregation_service import set_global_proxy_config
import telegram_proxy_payload_service
from telegram_proxy_config_service import (
    apply_proxy_state_update,
    delete_proxy_config,
    get_proxy_config,
    write_proxy_config,
)
from telegram_proxy_mode_service import (
    build_telethon_proxy as build_telethon_proxy,
    determine_active_proxy_config,
)
from telegram_proxy_probe_service import (
    check_google_connectivity,
    test_proxy_payload as test_proxy_payload,
)


GLOBAL_PROXY_CONFIG = None

__all__ = [
    "build_telethon_proxy",
    "delete_proxy_payload",
    "detect_connection_mode",
    "get_active_proxy_config",
    "get_proxy_payload",
    "set_proxy_payload",
    "test_proxy_payload",
    "update_proxy_state_payload",
]


def get_active_proxy_config() -> dict | None:
    return GLOBAL_PROXY_CONFIG


async def detect_connection_mode(
    *,
    db_path: str = DB_PATH,
    get_proxy_config_fn: Callable[[str], Awaitable[dict | None]] = get_proxy_config,
    check_connectivity_fn: Callable[[dict | None], Awaitable[bool]] = check_google_connectivity,
    set_search_proxy_config_fn: Callable[[dict | None], None] = set_global_proxy_config,
) -> None:
    global GLOBAL_PROXY_CONFIG
    GLOBAL_PROXY_CONFIG = await determine_active_proxy_config(
        db_path=db_path,
        get_proxy_config_fn=get_proxy_config_fn,
        check_connectivity_fn=check_connectivity_fn,
    )
    set_search_proxy_config_fn(GLOBAL_PROXY_CONFIG)


async def get_proxy_payload(
    *,
    db_path: str = DB_PATH,
    get_proxy_config_fn: Callable[[str], Awaitable[dict | None]] = get_proxy_config,
    get_active_proxy_config_fn: Callable[[], dict | None] = get_active_proxy_config,
) -> dict:
    return await telegram_proxy_payload_service.get_proxy_payload(
        db_path=db_path,
        get_proxy_config_fn=get_proxy_config_fn,
        get_active_proxy_config_fn=get_active_proxy_config_fn,
    )


async def set_proxy_payload(
    config: ProxyConfig,
    *,
    restart_client_fn: Callable[[], Awaitable[None]],
    db_path: str = DB_PATH,
    detect_connection_mode_fn: Callable[..., Awaitable[None]] = detect_connection_mode,
    get_active_proxy_config_fn: Callable[[], dict | None] = get_active_proxy_config,
) -> dict:
    return await telegram_proxy_payload_service.set_proxy_payload(
        config,
        restart_client_fn=restart_client_fn,
        db_path=db_path,
        write_proxy_config_fn=write_proxy_config,
        detect_connection_mode_fn=detect_connection_mode_fn,
        get_active_proxy_config_fn=get_active_proxy_config_fn,
    )


async def update_proxy_state_payload(
    state: ProxyStateUpdate,
    *,
    restart_client_fn: Callable[[], Awaitable[None]],
    db_path: str = DB_PATH,
    get_proxy_config_fn: Callable[[str], Awaitable[dict | None]] = get_proxy_config,
    detect_connection_mode_fn: Callable[..., Awaitable[None]] = detect_connection_mode,
    get_active_proxy_config_fn: Callable[[], dict | None] = get_active_proxy_config,
) -> dict:
    return await telegram_proxy_payload_service.update_proxy_state_payload(
        state,
        restart_client_fn=restart_client_fn,
        db_path=db_path,
        get_proxy_config_fn=get_proxy_config_fn,
        apply_proxy_state_update_fn=apply_proxy_state_update,
        write_proxy_config_fn=write_proxy_config,
        detect_connection_mode_fn=detect_connection_mode_fn,
        get_active_proxy_config_fn=get_active_proxy_config_fn,
    )


async def delete_proxy_payload(
    *,
    restart_client_fn: Callable[[], Awaitable[None]],
    db_path: str = DB_PATH,
    detect_connection_mode_fn: Callable[..., Awaitable[None]] = detect_connection_mode,
) -> dict:
    return await telegram_proxy_payload_service.delete_proxy_payload(
        restart_client_fn=restart_client_fn,
        db_path=db_path,
        delete_proxy_config_fn=delete_proxy_config,
        detect_connection_mode_fn=detect_connection_mode_fn,
    )
