# -*- coding: utf-8 -*-
import asyncio

import aiohttp
from fastapi import HTTPException

from config import TMDB_API_KEY
from structured_logging import log_event


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


async def fetch_tmdb_json(endpoint: str, params: dict | None = None, proxy_config: dict | None = None) -> dict:
    if not TMDB_API_KEY:
        raise HTTPException(status_code=400, detail="未配置 TMDB_API_KEY")
    query_params = {
        "api_key": TMDB_API_KEY,
        "language": "zh-CN",
        **(params or {}),
    }
    connector, request_kwargs = build_proxy_request_options(proxy_config)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=12)) as session:
        async with session.get(
            f"https://api.themoviedb.org/3/{endpoint.lstrip('/')}",
            params=query_params,
            **request_kwargs,
        ) as response:
            if response.status >= 400:
                raise HTTPException(status_code=502, detail="TMDB 请求失败")
            return await response.json()


async def fetch_tmdb_tv_episode_targets(
    tmdb_id: int | None,
    proxy_config: dict | None = None,
) -> dict[int, set[int]]:
    if not tmdb_id:
        return {}
    try:
        data = await fetch_tmdb_json(f"tv/{tmdb_id}", proxy_config=proxy_config)
    except Exception as exc:
        log_event("tmdb.tv_episode_targets.fetch_failed", "warning", tmdb_id=tmdb_id, error=str(exc))
        return {}

    targets: dict[int, set[int]] = {}
    for season in data.get("seasons", []):
        season_number = season.get("season_number")
        episode_count = int(season.get("episode_count") or 0)
        if not season_number or episode_count <= 0:
            continue
        targets[int(season_number)] = set(range(1, episode_count + 1))
    return targets


def _tmdb_image_url(path: str | None, size: str = "w500") -> str | None:
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else None


def _tmdb_backdrop_url(path: str | None, size: str = "w780") -> str | None:
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else None


def _year_from_date(value: str | None) -> int | None:
    value = value or ""
    return int(value[:4]) if value[:4].isdigit() else None


def _normalize_genres(data: dict) -> list[str]:
    return [item.get("name") for item in data.get("genres", []) if item.get("name")]


def normalize_tmdb_episode_marker(item: dict | None) -> dict | None:
    if not isinstance(item, dict):
        return None
    season_number = item.get("season_number")
    episode_number = item.get("episode_number")
    if not season_number or not episode_number:
        return None
    return {
        "season_number": int(season_number),
        "episode_number": int(episode_number),
        "name": item.get("name") or "",
        "air_date": item.get("air_date") or None,
        "overview": item.get("overview") or "",
    }


def normalize_tmdb_season_episode(item: dict | None) -> dict | None:
    if not isinstance(item, dict):
        return None
    episode_number = item.get("episode_number")
    if not episode_number:
        return None
    return {
        "episode_number": int(episode_number),
        "name": item.get("name") or f"第 {int(episode_number)} 集",
        "air_date": item.get("air_date") or None,
        "overview": item.get("overview") or "",
        "still_url": _tmdb_image_url(item.get("still_path")),
        "runtime": item.get("runtime") or None,
        "vote_average": item.get("vote_average") or 0,
    }


def normalize_tmdb_season_detail(data: dict) -> list[dict]:
    episodes = []
    for episode in data.get("episodes") or []:
        normalized = normalize_tmdb_season_episode(episode)
        if normalized:
            episodes.append(normalized)
    episodes.sort(key=lambda item: item["episode_number"])
    return episodes


def normalize_tmdb_tv_detail(data: dict) -> dict:
    seasons = []
    for season in data.get("seasons") or []:
        season_number = season.get("season_number")
        episode_count = int(season.get("episode_count") or 0)
        if season_number is None or int(season_number) == 0 or episode_count <= 0:
            continue
        seasons.append({
            "season_number": int(season_number),
            "name": season.get("name") or f"第 {int(season_number)} 季",
            "episode_count": episode_count,
            "air_date": season.get("air_date") or None,
            "overview": season.get("overview") or "",
            "poster_url": _tmdb_image_url(season.get("poster_path")),
            "episodes": season.get("episodes") or [],
        })
    seasons.sort(key=lambda item: item["season_number"])
    first_air_date = data.get("first_air_date") or ""
    return {
        "tmdb_id": data.get("id"),
        "tmdb_type": "tv",
        "title": data.get("name") or data.get("original_name") or "",
        "original_title": data.get("original_name") or "",
        "year": _year_from_date(first_air_date),
        "status": data.get("status") or "",
        "first_air_date": first_air_date or None,
        "last_air_date": data.get("last_air_date") or None,
        "release_date": first_air_date or None,
        "overview": data.get("overview") or "",
        "poster_url": _tmdb_image_url(data.get("poster_path")),
        "backdrop_url": _tmdb_backdrop_url(data.get("backdrop_path")),
        "vote_average": data.get("vote_average") or 0,
        "vote_count": data.get("vote_count") or 0,
        "genres": _normalize_genres(data),
        "search_keyword": f"{data.get('name') or data.get('original_name') or ''} {_year_from_date(first_air_date) or ''}".strip(),
        "seasons": seasons,
        "last_episode_to_air": normalize_tmdb_episode_marker(data.get("last_episode_to_air")),
        "next_episode_to_air": normalize_tmdb_episode_marker(data.get("next_episode_to_air")),
    }


async def fetch_tmdb_tv_detail(tmdb_id: int, proxy_config: dict | None = None) -> dict:
    data = await fetch_tmdb_json(f"tv/{int(tmdb_id)}", proxy_config=proxy_config)
    payload = normalize_tmdb_tv_detail(data)
    seasons = payload.get("seasons") or []
    if not seasons:
        return payload

    semaphore = asyncio.Semaphore(4)

    async def fetch_season_episodes(season: dict) -> tuple[int, list[dict]]:
        season_number = int(season["season_number"])
        try:
            async with semaphore:
                season_data = await fetch_tmdb_json(
                    f"tv/{int(tmdb_id)}/season/{season_number}",
                    proxy_config=proxy_config,
                )
            return season_number, normalize_tmdb_season_detail(season_data)
        except Exception as exc:
            log_event(
                "tmdb.tv_season_detail.fetch_failed",
                "warning",
                tmdb_id=tmdb_id,
                season_number=season_number,
                error=str(exc),
            )
            return season_number, []

    season_episode_pairs = await asyncio.gather(*(fetch_season_episodes(season) for season in seasons))
    episodes_by_season = {season_number: episodes for season_number, episodes in season_episode_pairs}
    for season in seasons:
        season["episodes"] = episodes_by_season.get(int(season["season_number"]), [])
    return payload


def normalize_tmdb_movie_detail(data: dict) -> dict:
    release_date = data.get("release_date") or ""
    title = data.get("title") or data.get("original_title") or ""
    year = _year_from_date(release_date)
    return {
        "tmdb_id": data.get("id"),
        "tmdb_type": "movie",
        "title": title,
        "original_title": data.get("original_title") or "",
        "year": year,
        "status": data.get("status") or "",
        "release_date": release_date or None,
        "overview": data.get("overview") or "",
        "poster_url": _tmdb_image_url(data.get("poster_path")),
        "backdrop_url": _tmdb_backdrop_url(data.get("backdrop_path")),
        "vote_average": data.get("vote_average") or 0,
        "vote_count": data.get("vote_count") or 0,
        "runtime": data.get("runtime") or None,
        "genres": _normalize_genres(data),
        "search_keyword": f"{title} {year or ''}".strip(),
    }


async def fetch_tmdb_media_detail(media_type: str, tmdb_id: int, proxy_config: dict | None = None) -> dict:
    media_type = (media_type or "").strip().lower()
    if media_type == "tv":
        return await fetch_tmdb_tv_detail(tmdb_id, proxy_config)
    if media_type == "movie":
        data = await fetch_tmdb_json(f"movie/{int(tmdb_id)}", proxy_config=proxy_config)
        return normalize_tmdb_movie_detail(data)
    raise HTTPException(status_code=400, detail="TMDB 类型只能是 movie 或 tv")


async def fetch_tmdb_tv_episode_total(tmdb_id: int | None, proxy_config: dict | None = None) -> int:
    targets = await fetch_tmdb_tv_episode_targets(tmdb_id, proxy_config)
    return sum(len(episodes) for episodes in targets.values())


def normalize_tmdb_wall_item(item: dict, fallback_type: str | None = None) -> dict | None:
    media_type = item.get("media_type") or fallback_type
    if media_type not in {"movie", "tv"}:
        return None
    title = item.get("title") or item.get("name")
    original_title = item.get("original_title") or item.get("original_name")
    date = item.get("release_date") or item.get("first_air_date") or ""
    year = int(date[:4]) if date[:4].isdigit() else None
    poster_path = item.get("poster_path")
    if not title or not poster_path:
        return None
    search_keyword = f"{title} {year}" if year else title
    return {
        "tmdb_id": item.get("id"),
        "tmdb_type": media_type,
        "title": title,
        "original_title": original_title,
        "year": year,
        "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}",
        "overview": item.get("overview") or "",
        "vote_average": item.get("vote_average") or 0,
        "release_date": date,
        "search_keyword": search_keyword,
    }
