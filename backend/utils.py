# -*- coding: utf-8 -*-
import hashlib
import re
from urllib.parse import parse_qs, urlparse, urlencode


def hostname_matches(host: str, allowed_domains: tuple[str, ...]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def is_safe_external_url(url: str, allowed_schemes: set[str] | None = None) -> bool:
    if not url:
        return False
    allowed_schemes = allowed_schemes or {"http", "https", "magnet", "ed2k"}
    lower = url.lower()
    if lower.startswith(("magnet:", "ed2k:")):
        return lower.split(":", 1)[0] in allowed_schemes
    parsed = urlparse(url)
    return parsed.scheme in allowed_schemes and bool(parsed.netloc)


def append_query_param(url: str, key: str, value: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({key: value})}"


def safe_error_detail(default: str = "请求处理失败") -> str:
    return default


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def safe_task_result_link(url: str) -> str:
    link_hash = stable_hash(url or "")
    if not url:
        return f"***{link_hash}"
    lower = url.lower()
    if lower.startswith(("magnet:", "ed2k:")):
        return f"{lower.split(':', 1)[0]}:***{link_hash}"
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/***{link_hash}"
    return f"***{link_hash}"


def normalize_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", (value or "").lower(), flags=re.UNICODE)


def normalize_channel_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith(("http://", "https://")):
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")
        if path_parts and path_parts[0]:
            return path_parts[0]
    if url.startswith("t.me/"):
        return url.split("/")[1].strip()
    if url.startswith("@"):
        return url[1:]
    return url


def classify_resource_url(url: str) -> str:
    lower = url.lower()
    host = urlparse(url).netloc.lower() if not lower.startswith(("magnet:", "ed2k:")) else ""
    if lower.startswith("magnet:"):
        return "magnet"
    if lower.startswith("ed2k:"):
        return "ed2k"
    if hostname_matches(host, ("115.com", "115cdn.com", "anxia.com")):
        return "115"
    if hostname_matches(host, ("pan.quark.cn",)):
        return "quark"
    if hostname_matches(host, ("pan.baidu.com", "yun.baidu.com")):
        return "baidu"
    if hostname_matches(host, ("aliyundrive.com", "alipan.com")):
        return "aliyun"
    return "others"


def extract_access_code(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r"(?:提取码|访问码|密码|pwd|code|码)\s*[:： ]?\s*([A-Za-z0-9]{3,8})", text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_resource_links_from_text(text: str) -> list[dict]:
    if not text:
        return []
    patterns = [
        r"https?://[^\s\"'<>）)】]+",
        r"magnet:\?xt=[^\s\"'<>）)】]+",
        r"ed2k://[^\s\"'<>）)】]+",
    ]
    seen = set()
    links = []
    code = extract_access_code(text)
    for pattern in patterns:
        for raw_url in re.findall(pattern, text, flags=re.IGNORECASE):
            url = raw_url.rstrip(".,，。;；")
            if url in seen:
                continue
            seen.add(url)
            link_type = classify_resource_url(url)
            if link_type == "others" and "t.me/" in url.lower():
                continue
            links.append({"url": url, "type": link_type, "password": code})
    return links


def normalize_cloud_types(cloud_types: list[str] | None) -> set[str]:
    valid = {"115", "magnet", "ed2k", "quark", "baidu", "aliyun", "others"}
    if not cloud_types:
        return valid
    selected = {item.strip().lower() for item in cloud_types if item and item.strip()}
    return selected & valid or valid


def link_with_password(url: str, password: str | None) -> str:
    clean = (url or "").strip()
    code = (password or "").strip()
    if not clean or not code:
        return clean
    if code.lower() in clean.lower():
        return clean
    parsed = urlparse(clean)
    if parse_qs(parsed.query).get("password") or parse_qs(parsed.query).get("pwd"):
        return clean
    return append_query_param(clean, "password", code)
