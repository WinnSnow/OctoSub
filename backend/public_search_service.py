# -*- coding: utf-8 -*-
import re
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

from channel_repository import list_channel_rows
from config import DB_PATH, PUBLIC_SEARCH_CHANNELS
from title_utils import extract_display_title
from utils import (
    classify_resource_url,
    extract_access_code,
    extract_resource_links_from_text,
    normalize_channel_url,
)


async def get_default_public_channels() -> list[str]:
    channels = [row["url"] for row in await list_channel_rows(db_path=DB_PATH, order_by_id=True)]
    if channels:
        return channels
    return PUBLIC_SEARCH_CHANNELS


def parse_public_search_html(channel: str, html: str, selected_types: set[str]) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for widget in soup.select(".tgme_widget_message_wrap"):
        message = widget.select_one(".tgme_widget_message")
        text_node = widget.select_one(".tgme_widget_message_text")
        if not message or not text_node:
            continue

        text = text_node.get_text("\n", strip=True)
        title = extract_display_title(text, "无标题")
        links = []
        for link in text_node.find_all("a", href=True):
            href = link["href"].strip()
            if href.startswith("http") or href.startswith(("magnet:", "ed2k:")):
                links.append(href)
        links.extend([item["url"] for item in extract_resource_links_from_text(text)])

        unique_links = []
        seen = set()
        access_code = extract_access_code(text)
        for url in links:
            clean_url = url.rstrip(".,，。;；")
            link_type = classify_resource_url(clean_url)
            if link_type not in selected_types:
                continue
            if clean_url in seen:
                continue
            seen.add(clean_url)
            unique_links.append({"url": clean_url, "type": link_type, "password": access_code})

        if not unique_links:
            continue

        image_node = widget.select_one(".tgme_widget_message_photo_wrap")
        image_url = None
        if image_node and image_node.get("style"):
            image_match = re.search(r"url\(['\"]?([^'\")]+)", image_node.get("style", ""))
            if image_match:
                image_url = image_match.group(1)

        time_node = widget.select_one("time")
        message_link_node = widget.select_one(".tgme_widget_message_date")
        publish_date = time_node.get("datetime") if time_node else None
        message_link = message_link_node.get("href") if message_link_node else None
        link_types = sorted({link["type"] for link in unique_links})

        results.append({
            "id": message.get("data-post") or f"{channel}-{len(results)}",
            "title": title,
            "channel_name": channel,
            "publish_date": publish_date,
            "description": text[:1000],
            "raw_text": text,
            "image_url": image_url,
            "message_link": message_link,
            "resource_url": unique_links[0]["url"],
            "link_type": unique_links[0]["type"],
            "link_types": link_types,
            "links": unique_links,
            "access_code": access_code,
            "source": "public_realtime",
        })
    return results


def build_proxy_request_options(proxy_config: dict | None) -> tuple[object | None, dict]:
    connector = None
    request_kwargs = {}
    if proxy_config:
        auth_part = f"{proxy_config.get('username')}:{proxy_config.get('password')}@" if proxy_config.get("username") else ""
        proxy_url = f"{proxy_config['protocol']}://{auth_part}{proxy_config['host']}:{proxy_config['port']}"
        if proxy_config["protocol"].startswith("socks"):
            from aiohttp_socks import ProxyConnector
            connector = ProxyConnector.from_url(proxy_url)
        else:
            request_kwargs["proxy"] = proxy_url
    return connector, request_kwargs


async def fetch_public_channel_search(
    channel: str,
    keyword: str,
    selected_types: set[str],
    proxy_config: dict | None = None,
    timeout_seconds: int = 8,
) -> dict:
    normalized_channel = normalize_channel_url(channel)
    url = f"https://t.me/s/{normalized_channel}?q={quote(keyword)}"
    connector, request_kwargs = build_proxy_request_options(proxy_config)

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TGWebViewSearch/1.0)"}
    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        async with session.get(url, **request_kwargs) as response:
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            html = await response.text()
    return {
        "channel": normalized_channel,
        "results": parse_public_search_html(normalized_channel, html, selected_types),
    }
