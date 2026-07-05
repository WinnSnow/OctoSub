# -*- coding: utf-8 -*-
from collections.abc import Callable

from telegram_service import get_telegram_client


class TelegramScrapeUnavailable(RuntimeError):
    pass


async def ensure_telegram_ready(
    *,
    get_client_fn: Callable[[], object | None] = get_telegram_client,
):
    client = get_client_fn()
    if not client:
        raise TelegramScrapeUnavailable("Telegram API 未配置，无法抓取频道。")

    if not client.is_connected():
        try:
            await client.connect()
        except Exception as exc:
            raise TelegramScrapeUnavailable("Telegram 客户端连接失败，请检查代理配置或重启后端。") from exc

    try:
        if not await client.is_user_authorized():
            raise TelegramScrapeUnavailable("Telegram 未登录，请先到 Telegram 账号管理页面完成登录。")
    except TelegramScrapeUnavailable:
        raise
    except Exception as exc:
        raise TelegramScrapeUnavailable("无法确认 Telegram 登录状态，请重置会话后重新登录。") from exc

    return client
