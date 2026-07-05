# -*- coding: utf-8 -*-
"""
Telegram proxy connectivity and probe helpers.
"""
import aiohttp
from fastapi import HTTPException

from schemas import ProxyConfig
from structured_logging import log_event

GOOGLE_TEST_URL = "https://www.google.com"


def build_proxy_url(proxy_config: dict) -> str:
    auth_part = f"{proxy_config.get('username')}:{proxy_config.get('password')}@" if proxy_config.get("username") else ""
    return f"{proxy_config['protocol']}://{auth_part}{proxy_config['host']}:{proxy_config['port']}"


async def check_google_connectivity(proxy_config: dict | None = None) -> bool:
    connector = None
    request_kwargs = {}

    if proxy_config:
        try:
            proxy_url = build_proxy_url(proxy_config)
            if proxy_config["protocol"].startswith("socks"):
                from aiohttp_socks import ProxyConnector

                connector = ProxyConnector.from_url(proxy_url)
            else:
                request_kwargs["proxy"] = proxy_url
        except Exception as exc:
            log_event("telegram.proxy.parse_failed", "warning", error=str(exc), proxy_config=proxy_config)
            return False

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(GOOGLE_TEST_URL, **request_kwargs) as resp:
                return resp.status == 200
    except Exception:
        return False


async def test_proxy_payload(config: ProxyConfig) -> dict:
    proxy_url = build_proxy_url(config.model_dump())

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        if config.protocol.startswith("socks"):
            from aiohttp_socks import ProxyConnector

            connector = ProxyConnector.from_url(proxy_url)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(GOOGLE_TEST_URL) as resp:
                    resp.raise_for_status()
        else:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(GOOGLE_TEST_URL, proxy=proxy_url) as resp:
                    resp.raise_for_status()

        return {"status": "success", "message": f"连接成功！已成功访问 {GOOGLE_TEST_URL}"}
    except Exception as exc:
        log_event(
            "telegram.proxy.test_failed",
            "warning",
            error=str(exc),
            protocol=config.protocol,
            host=config.host,
            port=config.port,
        )
        raise HTTPException(status_code=400, detail="连接失败: 无法连接到代理服务器或目标地址不可达") from exc
