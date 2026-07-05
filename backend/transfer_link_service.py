# -*- coding: utf-8 -*-
import html
import re
from urllib.parse import parse_qs, urlparse


def extract_115_share_code(link: str | None) -> str | None:
    if not link:
        return None
    match = re.search(r"https?://(?:115cdn\.com|115\.com)/s/([^/?#\s&]+)", html.unescape(link))
    return match.group(1) if match else None


def extract_115_share_password(link: str | None) -> str | None:
    if not link:
        return None
    parsed = urlparse(html.unescape(link))
    query = parse_qs(parsed.query)
    for key in ("password", "pwd", "pass", "code"):
        value = query.get(key)
        if value:
            return value[0]
    return None
