# -*- coding: utf-8 -*-


def poster_url_from_path(path: str | None) -> str | None:
    return f"https://image.tmdb.org/t/p/w500{path}" if path else None


def tmdb_proxy_options(proxy_config: dict | None) -> tuple[object | None, dict]:
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


def normalize_manual_tmdb_result(item: dict, media_type: str) -> dict | None:
    if not item.get("poster_path"):
        return None

    title = item.get("title") or item.get("name")
    date = item.get("release_date") or item.get("first_air_date")
    year = date[:4] if date else "未知年份"
    return {
        "id": item["id"],
        "tmdb_id": item["id"],
        "title": title,
        "year": year,
        "type": "电影" if media_type == "movie" else "剧集",
        "media_type": media_type,
        "tmdb_type": media_type,
        "release_date": date or None,
        "poster_url": poster_url_from_path(item["poster_path"]),
        "overview": item.get("overview", "")[:100] + "...",
        "vote_average": item.get("vote_average") or 0,
        "vote_count": item.get("vote_count") or 0,
    }
