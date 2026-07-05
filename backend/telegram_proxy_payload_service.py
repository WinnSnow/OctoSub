# -*- coding: utf-8 -*-
from collections.abc import Awaitable, Callable

from config import DB_PATH
from schemas import ProxyConfig, ProxyStateUpdate
from telegram_proxy_config_service import (
    apply_proxy_state_update,
    delete_proxy_config,
    get_proxy_config,
    write_proxy_config,
)


def system_mode_from_active(active_proxy_config: dict | None) -> str:
    return "proxy" if active_proxy_config else "direct"


def localized_mode_from_active(active_proxy_config: dict | None) -> str:
    return "代理" if active_proxy_config else "直连"


def mask_proxy_password(value: str | None, *, visible: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible:
        return "****"
    return f"****{text[-visible:]}"


def public_proxy_config(config: dict | None) -> dict:
    payload = dict(config or {})
    password = payload.pop("password", "")
    payload["password_configured"] = bool(password)
    payload["password_masked"] = mask_proxy_password(password)
    return payload


async def get_proxy_payload(
    *,
    db_path: str = DB_PATH,
    get_proxy_config_fn: Callable[[str], Awaitable[dict | None]] = get_proxy_config,
    get_active_proxy_config_fn: Callable[[], dict | None],
) -> dict:
    config = await get_proxy_config_fn(db_path)
    response = public_proxy_config(config)
    response["system_mode"] = system_mode_from_active(get_active_proxy_config_fn())
    return response


async def set_proxy_payload(
    config: ProxyConfig,
    *,
    restart_client_fn: Callable[[], Awaitable[None]],
    db_path: str = DB_PATH,
    write_proxy_config_fn: Callable[[dict, str], Awaitable[None]] = write_proxy_config,
    detect_connection_mode_fn: Callable[..., Awaitable[None]],
    get_active_proxy_config_fn: Callable[[], dict | None],
) -> dict:
    await write_proxy_config_fn(config.model_dump(), db_path)

    await detect_connection_mode_fn(db_path=db_path)
    await restart_client_fn()

    mode = localized_mode_from_active(get_active_proxy_config_fn())
    return {"message": f"代理配置已保存。当前系统运行于: {mode}模式"}


async def update_proxy_state_payload(
    state: ProxyStateUpdate,
    *,
    restart_client_fn: Callable[[], Awaitable[None]],
    db_path: str = DB_PATH,
    get_proxy_config_fn: Callable[[str], Awaitable[dict | None]] = get_proxy_config,
    apply_proxy_state_update_fn: Callable[[dict | None, ProxyStateUpdate], ProxyConfig] = apply_proxy_state_update,
    write_proxy_config_fn: Callable[[dict, str], Awaitable[None]] = write_proxy_config,
    detect_connection_mode_fn: Callable[..., Awaitable[None]],
    get_active_proxy_config_fn: Callable[[], dict | None],
) -> dict:
    config = await get_proxy_config_fn(db_path)
    validated_config = apply_proxy_state_update_fn(config, state)
    await write_proxy_config_fn(validated_config.model_dump(), db_path)

    await detect_connection_mode_fn(db_path=db_path)
    await restart_client_fn()

    active_config = get_active_proxy_config_fn()
    mode = localized_mode_from_active(active_config)
    status = "已启用" if validated_config.enabled else "已停用"
    return {
        "message": f"代理状态已更新：{status}，当前系统运行于: {mode}模式",
        "system_mode": system_mode_from_active(active_config),
        "config": public_proxy_config(validated_config.model_dump()),
    }


async def delete_proxy_payload(
    *,
    restart_client_fn: Callable[[], Awaitable[None]],
    db_path: str = DB_PATH,
    delete_proxy_config_fn: Callable[[str], Awaitable[None]] = delete_proxy_config,
    detect_connection_mode_fn: Callable[..., Awaitable[None]],
) -> dict:
    await delete_proxy_config_fn(db_path)

    await detect_connection_mode_fn(db_path=db_path)
    await restart_client_fn()

    return {"message": "代理配置已移除。系统已尝试切换回直连模式。"}
