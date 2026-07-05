# -*- coding: utf-8 -*-
import asyncio
import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from message_extraction_service import extract_links, extract_links_from_telegraph
from structured_logging import log_event
from utils import append_query_param, hostname_matches, link_with_password


INTERMEDIATE_LINK_CONCURRENCY = 5
INTERMEDIATE_LINK_TIMEOUT_SECONDS = 8
_INTERMEDIATE_LINK_SEMAPHORE = asyncio.Semaphore(INTERMEDIATE_LINK_CONCURRENCY)

URL_RE = re.compile(
    r"https?://[^\s\"'<>）)】|｜]+|ed2k://[^\s\"'<>）)】|｜]+|magnet:\?xt=[^\s\"'<>）)】|｜]+",
    re.IGNORECASE,
)
RESOURCE_DOMAINS = (
    "115.com",
    "115cdn.com",
    "anxia.com",
    "pan.quark.cn",
    "pan.baidu.com",
    "pan.xunlei.com",
    "hdhive.com",
    "hdhive.online",
    "alipan.com",
    "aliyundrive.com",
    "cloud.189.cn",
)
INTERMEDIATE_DOMAINS = (
    "telegra.ph",
    "graph.org",
    "pastebin.com",
    "justpaste.it",
)


def dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _clean_url(url: str | None) -> str:
    return (url or "").strip().rstrip(".,，。;；|｜)#")


def _regex_urls(pattern: re.Pattern, text: str | None) -> list[str]:
    if not text:
        return []
    urls = []
    for match in pattern.findall(text):
        if isinstance(match, tuple):
            url = next((part for part in match if part), "")
        else:
            url = match
        url = _clean_url(url)
        if url:
            urls.append(url)
    return urls


def _url_host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ""


def _is_resource_url(url: str) -> bool:
    lower = url.lower()
    if lower.startswith(("magnet:", "ed2k://")):
        return True
    return hostname_matches(_url_host(url), RESOURCE_DOMAINS)


def _is_intermediate_url(url: str) -> bool:
    return hostname_matches(_url_host(url), INTERMEDIATE_DOMAINS)


def extract_direct_resource_links(
    message,
    *,
    extract_links_fn: Callable[[object], list[dict]] = extract_links,
    append_query_param_fn: Callable[[str, str, str], str] = append_query_param,
    text: str | None = None,
) -> list[str]:
    """Extract resource links that do not require fetching intermediate pages."""
    direct_links = []
    for item in extract_links_fn(message):
        if item["type"] != "115":
            continue
        final_url = link_with_password(_clean_url(item["url"]), item["password"])
        direct_links.append(final_url)

    regex_found_links = [
        url
        for url in _regex_urls(URL_RE, text if text is not None else message.text)
        if _is_resource_url(url)
    ]
    direct_links.extend(regex_found_links)
    return dedupe_preserve_order(direct_links)


def extract_intermediate_link_candidates(
    message,
    *,
    extract_links_fn: Callable[[object], list[dict]] = extract_links,
    text: str | None = None,
) -> list[str]:
    """Extract intermediate page URLs without deduping across message contexts."""
    intermediate_links = []
    for item in extract_links_fn(message):
        if item["type"] == "intermediate":
            intermediate_links.append(_clean_url(item["url"]))
    intermediate_links.extend(
        url
        for url in _regex_urls(URL_RE, text if text is not None else message.text)
        if _is_intermediate_url(url)
    )
    return intermediate_links


def extract_link_candidates(
    message,
    *,
    extract_links_fn: Callable[[object], list[dict]] = extract_links,
    append_query_param_fn: Callable[[str, str, str], str] = append_query_param,
    text: str | None = None,
) -> dict:
    extracted_data = extract_links_fn(message)
    direct_links = []
    intermediate_links = []
    for item in extracted_data:
        if item["type"] == "115":
            final_url = link_with_password(_clean_url(item["url"]), item["password"])
            direct_links.append(final_url)
        elif item["type"] == "intermediate":
            intermediate_links.append(_clean_url(item["url"]))

    direct_links.extend(
        url
        for url in _regex_urls(URL_RE, text if text is not None else message.text)
        if _is_resource_url(url)
    )
    intermediate_links.extend(
        url
        for url in _regex_urls(URL_RE, text if text is not None else message.text)
        if _is_intermediate_url(url)
    )
    return {
        "direct_resource_links": dedupe_preserve_order(direct_links),
        "intermediate_links": intermediate_links,
    }


def has_resource_link_entrypoint(
    message,
    *,
    extract_links_fn: Callable[[object], list[dict]] = extract_links,
) -> bool:
    if any(item["type"] in {"115", "intermediate"} for item in extract_links_fn(message)):
        return True
    return bool(re.search(
        r"https?://pan\.quark\.cn/s/[\w\d]+|ed2k://[^\s]+|magnet:\?xt=[^\s]+",
        message.text or "",
    ))


async def extract_intermediate_links(
    intermediate_url: str,
    proxy_config: dict | None,
    *,
    extract_links_from_telegraph_fn: Callable[..., Awaitable[list[dict]]] = extract_links_from_telegraph,
    append_query_param_fn: Callable[[str, str, str], str] = append_query_param,
    stats: dict | None = None,
) -> list[str]:
    try:
        async with _INTERMEDIATE_LINK_SEMAPHORE:
            sub_links = await extract_links_from_telegraph_fn(
                intermediate_url,
                proxy_config,
                timeout_seconds=INTERMEDIATE_LINK_TIMEOUT_SECONDS,
            )
        if stats is not None:
            stats["intermediate_successes"] = int(stats.get("intermediate_successes") or 0) + 1
    except asyncio.TimeoutError:
        if stats is not None:
            stats["intermediate_timeouts"] = int(stats.get("intermediate_timeouts") or 0) + 1
        raise
    except Exception:
        if stats is not None:
            stats["intermediate_failures"] = int(stats.get("intermediate_failures") or 0) + 1
        raise

    final_links = []
    for sub_link in sub_links:
        final_url = link_with_password(_clean_url(sub_link["url"]), sub_link.get("password"))
        final_links.append(final_url)
    return final_links


async def resolve_intermediate_resource_links(
    intermediate_urls: list[str],
    proxy_config: dict | None,
    *,
    extract_links_from_telegraph_fn: Callable[..., Awaitable[list[dict]]] = extract_links_from_telegraph,
    append_query_param_fn: Callable[[str, str, str], str] = append_query_param,
    stats: dict | None = None,
) -> list[str]:
    """Resolve each intermediate URL occurrence; callers intentionally do not dedupe URLs."""
    tasks = [
        extract_intermediate_links(
            url,
            proxy_config,
            extract_links_from_telegraph_fn=extract_links_from_telegraph_fn,
            append_query_param_fn=append_query_param_fn,
            stats=stats,
        )
        for url in intermediate_urls
    ]
    if not tasks:
        return []
    settled_results = await asyncio.gather(*tasks, return_exceptions=True)
    links = []
    for result in settled_results:
        if isinstance(result, Exception):
            log_event(
                "scrape.intermediate.resolve_failed",
                "warning",
                error_type=type(result).__name__,
            )
            continue
        links.extend(result)
    return dedupe_preserve_order(links)


async def collect_resource_links(
    message,
    proxy_config: dict | None,
    *,
    extract_links_fn: Callable[[object], list[dict]] = extract_links,
    extract_links_from_telegraph_fn: Callable[..., Awaitable[list[dict]]] = extract_links_from_telegraph,
    append_query_param_fn: Callable[[str, str, str], str] = append_query_param,
) -> list[str]:
    extracted_data = extract_links_fn(message)
    all_found_links = []
    ordered_items = []
    intermediate_tasks = []

    for item in extracted_data:
        if item["type"] == "intermediate":
            task = extract_intermediate_links(
                _clean_url(item["url"]),
                proxy_config,
                extract_links_from_telegraph_fn=extract_links_from_telegraph_fn,
                append_query_param_fn=append_query_param_fn,
            )
            intermediate_tasks.append(task)
            ordered_items.append(("intermediate", task))
        elif item["type"] == "115":
            final_url = link_with_password(_clean_url(item["url"]), item["password"])
            ordered_items.append(("links", [final_url]))

    intermediate_results = {}
    if intermediate_tasks:
        settled_results = await asyncio.gather(*intermediate_tasks, return_exceptions=True)
        for task, result in zip(intermediate_tasks, settled_results, strict=True):
            if isinstance(result, Exception):
                log_event(
                    "scrape.intermediate.collect_failed",
                    "warning",
                    error_type=type(result).__name__,
                )
                intermediate_results[task] = []
                continue
            intermediate_results[task] = result

    for kind, value in ordered_items:
        if kind == "intermediate":
            all_found_links.extend(intermediate_results.get(value, []))
        else:
            all_found_links.extend(value)

    if not all_found_links:
        regex_found_links = re.findall(
            r"(https?://pan\.quark\.cn/s/[\w\d]+|ed2k://[^\s]+|magnet:\?xt=[^\s]+)",
            message.text,
        )
        all_found_links.extend(regex_found_links)

    return dedupe_preserve_order(all_found_links)
