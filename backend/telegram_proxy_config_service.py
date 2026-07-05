# -*- coding: utf-8 -*-
"""
Telegram proxy configuration persistence helpers.
"""
import json

from config import DB_PATH
from schemas import ProxyConfig, ProxyStateUpdate
from telegram_proxy_config_repository import delete_config_value, get_config_value, write_config_value


DEFAULT_PROXY_CONFIG = {
    "protocol": "socks5",
    "host": "127.0.0.1",
    "port": 7890,
    "username": "",
    "password": "",
    "enabled": True,
    "mode": "auto",
}


async def get_proxy_config(db_path: str = DB_PATH) -> dict | None:
    value = await get_config_value("proxy", db_path)
    return json.loads(value) if value else None


async def write_proxy_config(config: dict, db_path: str = DB_PATH) -> None:
    await write_config_value("proxy", json.dumps(config), db_path)


async def delete_proxy_config(db_path: str = DB_PATH) -> None:
    await delete_config_value("proxy", db_path)


def apply_proxy_state_update(config: dict | None, state: ProxyStateUpdate) -> ProxyConfig:
    updated = dict(config or DEFAULT_PROXY_CONFIG)
    if state.enabled is not None:
        updated["enabled"] = state.enabled
    if state.mode is not None:
        updated["mode"] = state.mode
    return ProxyConfig(**updated)
