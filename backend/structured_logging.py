# -*- coding: utf-8 -*-
import json
import logging
import os
import time
from collections import deque
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


LOGGER_NAME = "tg_web"
RECENT_EVENT_LIMIT = 200
_CONFIGURED = False
_RECENT_EVENTS = deque(maxlen=RECENT_EVENT_LIMIT)
SENSITIVE_FIELD_TOKENS = {
    "api_key",
    "apikey",
    "auth_secret",
    "authorization",
    "cookie",
    "encoding_aes_key",
    "password",
    "secret",
    "session",
    "token",
}
SENSITIVE_QUERY_KEYS = {"password", "pwd", "pass", "code", "token", "access_token", "api_key", "apikey", "secret"}
SENSITIVE_SHARE_HOSTS = {"115.com", "115cdn.com", "anxia.com"}
URL_PATTERN = re.compile(r"https?://[^\s\"'<>）)】]+")


def _configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    _CONFIGURED = True


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def redact_secret(value, *, visible: int = 4):
    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if len(text) <= visible:
        return "***"
    return f"***{text[-visible:]}"


def redact_url_password(value: str) -> str:
    if not isinstance(value, str) or "://" not in value:
        return value

    def _redact_single_url(url: str) -> str:
        try:
            parts = urlsplit(url)
            query_items = []
            changed = False
            for key, item_value in parse_qsl(parts.query, keep_blank_values=True):
                if key.lower() in SENSITIVE_QUERY_KEYS:
                    query_items.append((key, redact_secret(item_value)))
                    changed = True
                else:
                    query_items.append((key, item_value))
            netloc = parts.netloc
            if "@" in netloc:
                credentials, host = netloc.rsplit("@", 1)
                if ":" in credentials:
                    username, password = credentials.split(":", 1)
                    credentials = f"{username}:{redact_secret(password)}"
                    changed = True
                netloc = f"{credentials}@{host}"
            hostname = (parts.hostname or "").lower().rstrip(".")
            if hostname in SENSITIVE_SHARE_HOSTS or any(hostname.endswith(f".{host}") for host in SENSITIVE_SHARE_HOSTS):
                path_parts = parts.path.strip("/").split("/")
                if len(path_parts) >= 2 and path_parts[0].lower() == "s" and path_parts[1]:
                    parts = parts._replace(path="/s/***")
                    changed = True
            if not changed:
                return url
            return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query_items), parts.fragment))
        except Exception:
            return url

    if not value.startswith(("http://", "https://")):
        return URL_PATTERN.sub(lambda match: _redact_single_url(match.group(0)), value)

    try:
        redacted = _redact_single_url(value)
        if redacted != value:
            return redacted
        return URL_PATTERN.sub(lambda match: _redact_single_url(match.group(0)), value)
    except Exception:
        return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(token in normalized for token in SENSITIVE_FIELD_TOKENS)


def redact_mapping(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item_value in value.items():
            if _is_sensitive_key(str(key)):
                redacted[key] = redact_secret(item_value)
            else:
                redacted[key] = redact_mapping(item_value)
        return redacted
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_mapping(item) for item in value)
    if isinstance(value, set):
        return {redact_mapping(item) for item in value}
    if isinstance(value, str):
        return redact_url_password(value)
    return value


def log_event(event: str, level: str = "info", **fields) -> dict:
    _configure_logging()
    payload = {
        "event": event,
        "ts": round(time.time(), 3),
        **redact_mapping(fields),
    }
    levelno = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger(LOGGER_NAME).log(
        levelno,
        json.dumps(payload, ensure_ascii=False, default=_json_default, separators=(",", ":")),
    )
    _RECENT_EVENTS.append(payload.copy())
    return payload


def get_recent_events(limit: int = 20) -> list[dict]:
    limit = max(1, min(int(limit or 20), RECENT_EVENT_LIMIT))
    return list(_RECENT_EVENTS)[-limit:][::-1]


def clear_recent_events() -> None:
    _RECENT_EVENTS.clear()
