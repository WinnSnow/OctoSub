# -*- coding: utf-8 -*-
import re
from urllib.parse import parse_qs, urlparse

import aiohttp
from bs4 import BeautifulSoup
from telethon.tl.types import KeyboardButtonUrl, MessageEntityTextUrl, MessageEntityUrl

from media_text_rules import NEGATIVE_CONTENT_PATTERNS
from structured_logging import log_event
from utils import hostname_matches


PROMOTIONAL_MESSAGE_PATTERNS = (
    r"TG必备搜索引擎",
    r"Telegram必备的搜索引擎",
    r"新币搜",
    r"极搜",
    r"JISOU",
    r"快速搜索",
    r"#频道互推",
    r"#群组推荐",
    r"#互推",
    r"机场",
    r"Emby",
    r"公费服",
    r"永久网址",
    r"高端嫩模",
    r"劳力士",
    r"奔驰E300",
    r"首存",
    r"日存彩金",
    r"爆奖",
    r"百家乐",
    r"娱乐城",
    r"全网广告费",
    r"免实名",
    r"无需绑银行卡",
    r"钱包WG",
    r"Y3国际",
    r"球速[·・]?体育",
    r"182\s*体育",
    r"2026世界杯",
)

ALL_PROMOTIONAL_MESSAGE_PATTERNS = tuple(dict.fromkeys((
    *PROMOTIONAL_MESSAGE_PATTERNS,
    *NEGATIVE_CONTENT_PATTERNS,
)))


def is_promotional_message(title: str | None, raw_text: str | None) -> bool:
    """
    Detect channel ads, search-engine promos, cross-promotions, and gambling ads.
    Callers should combine this with a "no resource links found" check to avoid
    filtering legitimate resource posts that contain promotional footers.
    """
    text = "\n".join(part for part in (title or "", raw_text or "") if part)
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in ALL_PROMOTIONAL_MESSAGE_PATTERNS)


def extract_links(message):
    """
    Extract 115 and intermediate links from a Telegram message, including hidden
    links, inline keyboard buttons, plain text URLs, and nearby share passwords.
    """
    found_links = []
    seen_urls = set()

    for entity in getattr(message, "entities", None) or []:
        url = None
        if isinstance(entity, MessageEntityTextUrl):
            url = entity.url
        elif isinstance(entity, MessageEntityUrl):
            pass

        if url:
            found_links.append({"url": url.strip(), "source": "entity"})

    reply_markup = getattr(message, "reply_markup", None)
    if reply_markup and hasattr(reply_markup, "rows"):
        for row in reply_markup.rows:
            for button in row.buttons:
                if isinstance(button, KeyboardButtonUrl):
                    found_links.append({"url": button.url.strip(), "source": "button"})

    text_urls = re.findall(r"(https?://[^\s]+)", message.text or "")
    for url in text_urls:
        found_links.append({"url": url.strip(), "source": "text"})

    results = []
    domains_115 = ("115.com", "115cdn.com", "anxia.com")
    domains_intermediate = ("telegra.ph", "graph.org", "pastebin.com", "justpaste.it")

    for item in found_links:
        raw_url = item["url"]
        if raw_url in seen_urls:
            continue
        seen_urls.add(raw_url)

        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower()
        entry = {
            "type": "unknown",
            "url": raw_url,
            "password": None,
            "source": item["source"],
        }

        if hostname_matches(domain, domains_115):
            entry["type"] = "115"
            query = parse_qs(parsed.query)
            if "password" in query:
                entry["password"] = query["password"][0]
            elif "pickcode" in query:
                entry["password"] = query["pickcode"][0]
        elif hostname_matches(domain, domains_intermediate):
            entry["type"] = "intermediate"
        else:
            entry["type"] = "other"

        if entry["type"] in {"115", "intermediate"}:
            results.append(entry)

    global_password_match = re.search(
        r"(?:码|密码|pwd|code|访问码)\s*[:：]?\s*([a-z0-9]{4,})",
        message.text or "",
        re.IGNORECASE,
    )
    global_password = global_password_match.group(1) if global_password_match else None
    for entry in results:
        if entry["type"] == "115" and not entry["password"] and global_password:
            entry["password"] = global_password

    return results


async def extract_links_from_telegraph(
    telegraph_url: str,
    proxy_config: dict | None = None,
    timeout_seconds: int = 8,
) -> list[dict]:
    """
    Extract resource links from a Telegraph-like intermediate page.
    """
    log_event("message_extraction.telegraph.started", telegraph_url=telegraph_url)
    found_links = []
    seen_urls = set()
    try:
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

        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(telegraph_url, **request_kwargs) as response:
                response.raise_for_status()
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        text_content = str(soup)

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if ("115cdn.com" in href or "115.com" in href or href.startswith("ed2k://")) and href not in seen_urls:
                seen_urls.add(href)
                found_links.append({"url": href, "password": None})

        plain_text_links = re.findall(
            r"(https?://(?:[\w\.-]*(?:115cdn|115)\.com[^\s\"'<>]+)|ed2k://[^\s\"'<>]+|magnet:\?xt=[^\s\"'<>]+)",
            text_content,
        )
        for link in plain_text_links:
            if link not in seen_urls:
                seen_urls.add(link)
                found_links.append({"url": link, "password": None})

        page_password_match = re.search(
            r"(?:码|密码|pwd|code|访问码)\s*[:：]?\s*([a-z0-9]{4,})",
            soup.get_text(),
            re.IGNORECASE,
        )
        page_password = page_password_match.group(1) if page_password_match else None
        if page_password:
            for item in found_links:
                if "115" in item["url"] and "password" not in item["url"]:
                    item["password"] = page_password

        if found_links:
            log_event("message_extraction.telegraph.links_found", telegraph_url=telegraph_url, count=len(found_links))
        else:
            log_event("message_extraction.telegraph.no_links", telegraph_url=telegraph_url)
        return found_links
    except Exception as exc:
        log_event(
            "message_extraction.telegraph.failed",
            "warning",
            telegraph_url=telegraph_url,
            error_type=type(exc).__name__,
        )
        return []


def parse_structured_format(message):
    """
    Parse channel posts that include rating and description labels.
    """
    text = message.text
    if not text or ("评分：" not in text and "评分:" not in text) or ("简介：" not in text and "简介:" not in text):
        return None

    lines = text.split("\n")
    title = lines[0].strip()
    description = ""
    try:
        start_index = -1
        for index, line in enumerate(lines):
            if "评分" in line:
                start_index = index
                break
        if start_index != -1:
            relevant_lines = [line.strip() for line in lines[start_index:]]
            end_index = len(relevant_lines)
            for index, line in enumerate(relevant_lines):
                if "链接" in line or "投稿" in line or "http" in line:
                    end_index = index
                    break
            description = "\n".join(relevant_lines[:end_index])
    except Exception:
        pass

    return {"title": title, "description": description}


def filter_message_text(text: str) -> str:
    if not text:
        return ""
    return "\n".join([line.strip() for line in text.split("\n") if line.strip().startswith(("🏷", "📝", "🔖"))])
