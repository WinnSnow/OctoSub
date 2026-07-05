# -*- coding: utf-8 -*-
from config import DB_PATH, JELLYFIN_API_KEY, JELLYFIN_URL
from db import connect_db
from jellyfin_client import JellyfinClient, get_jellyfin_client, init_jellyfin_client
from utils import is_safe_external_url


def mask_config_secret(value: str | None, *, visible: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible:
        return "****"
    return f"****{text[-visible:]}"


async def get_jellyfin_config_values(include_defaults: bool = True) -> dict:
    async with connect_db(DB_PATH) as conn:
        async with conn.execute(
            "SELECT key, value FROM system_config WHERE key IN ('jellyfin_url', 'jellyfin_api_key')"
        ) as cursor:
            rows = await cursor.fetchall()

    config = {row[0]: row[1] for row in rows}
    if include_defaults:
        config["jellyfin_url"] = config.get("jellyfin_url") or JELLYFIN_URL
        config["jellyfin_api_key"] = config.get("jellyfin_api_key") or JELLYFIN_API_KEY
    return config


async def ensure_jellyfin_client():
    jellyfin = get_jellyfin_client()
    if jellyfin:
        return jellyfin

    config = await get_jellyfin_config_values(include_defaults=True)
    jellyfin_url = config.get("jellyfin_url")
    jellyfin_api_key = config.get("jellyfin_api_key")
    if jellyfin_url and jellyfin_api_key:
        init_jellyfin_client(jellyfin_url, jellyfin_api_key)
        return get_jellyfin_client()
    return None


async def save_jellyfin_config_values(url: str, api_key: str) -> None:
    async with connect_db(DB_PATH) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            ("jellyfin_url", url),
        )
        await conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            ("jellyfin_api_key", api_key),
        )
        await conn.commit()
    init_jellyfin_client(url, api_key)


async def get_jellyfin_status_payload() -> dict:
    config = await get_jellyfin_config_values(include_defaults=True)
    jellyfin_url = config.get("jellyfin_url")
    jellyfin_api_key = config.get("jellyfin_api_key")

    if not jellyfin_url or not jellyfin_api_key:
        return {
            "enabled": False,
            "configured": False,
            "connected": False,
            "message": "Jellyfin 未配置",
        }

    jellyfin = await ensure_jellyfin_client()
    if not jellyfin:
        return {
            "enabled": True,
            "configured": True,
            "connected": False,
            "message": "Jellyfin 客户端未初始化",
        }

    connected = await jellyfin.test_connection()
    return {
        "enabled": True,
        "configured": True,
        "connected": connected,
        "url": jellyfin_url,
        "message": "连接成功" if connected else "连接失败",
    }


async def test_jellyfin_config_payload(url: str | None = None, api_key: str | None = None) -> dict:
    url = (url or "").strip()
    api_key = (api_key or "").strip()
    if url or api_key:
        if not url or not api_key:
            return {"success": False, "connected": False, "message": "URL 和 API Key 不能为空"}
        if not is_safe_external_url(url, {"http", "https"}):
            return {"success": False, "connected": False, "message": "Jellyfin URL 格式无效"}
        jellyfin = JellyfinClient(url, api_key)
    else:
        jellyfin = await ensure_jellyfin_client()
        if not jellyfin:
            return {"success": False, "connected": False, "message": "Jellyfin 未配置"}

    connected = await jellyfin.test_connection()
    libraries = await jellyfin.get_libraries() if connected else []
    return {
        "success": connected,
        "connected": connected,
        "message": "连接成功" if connected else "连接失败",
        "libraries": libraries,
    }


async def get_jellyfin_config_payload() -> dict:
    config = await get_jellyfin_config_values(include_defaults=False)
    api_key = config.get("jellyfin_api_key", "")
    return {
        "url": config.get("jellyfin_url", ""),
        "api_key_configured": bool(api_key),
        "api_key_masked": mask_config_secret(api_key),
        "configured": bool(config.get("jellyfin_url") and api_key),
    }
