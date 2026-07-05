# -*- coding: utf-8 -*-
import json
import re

from media_parser import coerce_media_number, parse_and_generate_fingerprint, parse_media_title
from subscription_repository import list_subscription_state_rows
from title_utils import clean_media_identity_title, extract_episode_hint, normalize_subscription_key
from utils import stable_hash


def build_subscription_media_fingerprint(
    subscription_id: int | None,
    keyword: str,
    year: int | None,
    media_type: str | None,
    title: str,
    link: str,
) -> tuple[dict, str]:
    identity_title = clean_media_identity_title(keyword or title)
    if media_type == "movie":
        parsed = {
            "title": identity_title,
            "year": year,
            "type": "movie",
            "season": None,
            "episode": None,
        }
        if identity_title and year:
            return parsed, f"{identity_title}_Movie_{year}"
        if identity_title:
            return parsed, f"{identity_title}_Movie"

    parsed, fingerprint = parse_and_generate_fingerprint(clean_media_identity_title(title) or title)
    if not fingerprint:
        fingerprint = f"sub:{subscription_id}:{stable_hash(link)}"
    return parsed, fingerprint


def build_subscription_state_payload(row: dict | None) -> dict | None:
    if not row:
        return None
    raw_status = row.get("status") or "active"
    status = "paused" if raw_status != "completed" and not row.get("enabled", True) else raw_status
    current = int(row.get("progress_current") or 0)
    total = int(row.get("progress_total") or 0)
    media_type = row.get("tmdb_type") or row.get("media_type")
    try:
        episode_state = json.loads(row.get("episode_state_json") or "{}")
        if not isinstance(episode_state, dict):
            episode_state = {}
    except Exception:
        episode_state = {}
    if status == "completed":
        label = "已入库" if media_type == "movie" else "已完成"
        library_status = "in_library"
    elif status == "paused":
        label = "已暂停"
        library_status = "paused"
    else:
        label = f"{current}/{total}" if media_type == "tv" and total > 0 else "订阅中"
        library_status = "subscribed"
    return {
        "subscription_id": row.get("id"),
        "title": row.get("keyword"),
        "media_type": media_type,
        "status": status,
        "library_status": library_status,
        "label": label,
        "progress_current": current,
        "progress_total": total,
        "episode_state": episode_state,
        "completed_at": row.get("completed_at"),
    }


def _title_without_episode_noise(value: str | None) -> str:
    text = value or ""
    text = re.sub(r"\bS\d{1,2}\s*E\d{1,4}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:更新至|更至|更)\s*\d{1,4}\s*[集话話]?", " ", text)
    text = re.sub(r"第\s*\d{1,4}\s*[集话話]", " ", text)
    text = re.sub(r"\bEP?\s*\d{1,4}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return clean_media_identity_title(text)


def _subscription_title_keys(item: dict) -> list[str]:
    values = []
    for key in ("title", "library_check_title", "search_keyword", "subscription_keyword", "name"):
        value = item.get(key)
        if value:
            values.append(str(value))
            values.append(_title_without_episode_noise(str(value)))
            parsed = parse_media_title(str(value))
            if parsed.get("title"):
                values.append(str(parsed["title"]))
    keys = [normalize_subscription_key(value) for value in values if value]
    return list(dict.fromkeys(key for key in keys if key))


def _extract_item_episode(item: dict) -> tuple[int | None, int | None]:
    season = coerce_media_number(item.get("season")) or coerce_media_number(item.get("_target_season"))
    episode = coerce_media_number(item.get("episode")) or coerce_media_number(item.get("_target_episode"))
    if season and episode:
        return season, episode

    for key in ("title", "raw_text", "description", "content", "note"):
        hint_season, hint_episode = extract_episode_hint(item.get(key))
        if hint_episode:
            return season or hint_season or 1, episode or hint_episode
    return season, episode


def _exact_existing_episode_state(state: dict, season: int | None, episode: int | None) -> dict | None:
    if not season or not episode:
        return None
    episode_state = state.get("episode_state") if isinstance(state.get("episode_state"), dict) else {}
    existing = episode_state.get("existing_episodes") if isinstance(episode_state.get("existing_episodes"), dict) else {}
    existing_episodes = set()
    for item in existing.get(str(int(season)), []):
        episode_number = coerce_media_number(item)
        if episode_number:
            existing_episodes.add(int(episode_number))
    if int(episode) not in existing_episodes:
        return None
    exact_state = dict(state)
    exact_state.update({
        "status": "completed",
        "library_status": "in_library",
        "label": f"E{int(episode)} 已入库",
        "progress_current": 1,
        "progress_total": 1,
        "target_season": int(season),
        "target_episode": int(episode),
        "exact_episode_checked": True,
    })
    return exact_state


async def get_subscription_state_maps() -> tuple[dict[tuple[str, int], dict], dict[tuple[str, str, int | None], dict]]:
    rows = await list_subscription_state_rows()
    by_tmdb: dict[tuple[str, int], dict] = {}
    by_identity: dict[tuple[str, str, int | None], dict] = {}
    for row in rows:
        media_type = row.get("tmdb_type") or row.get("media_type")
        if media_type not in {"movie", "tv"}:
            continue
        state = build_subscription_state_payload(row)
        if not state:
            continue
        tmdb_id = row.get("tmdb_id")
        if tmdb_id:
            by_tmdb[(media_type, int(tmdb_id))] = state
        title_key = normalize_subscription_key(row.get("keyword"))
        if title_key:
            by_identity[(media_type, title_key, row.get("year"))] = state
            by_identity.setdefault((media_type, title_key, None), state)
    return by_tmdb, by_identity


def attach_subscription_state(item: dict, by_tmdb: dict, by_identity: dict) -> dict:
    item.pop("subscription_state", None)
    item.pop("library_status", None)
    tmdb_type = item.get("tmdb_type")
    if not tmdb_type and item.get("type") in {"电影", "剧集"}:
        tmdb_type = "movie" if item.get("type") == "电影" else "tv"
    tmdb_id = item.get("tmdb_id") or item.get("id")
    state = None
    if tmdb_type in {"movie", "tv"} and tmdb_id:
        try:
            state = by_tmdb.get((tmdb_type, int(tmdb_id)))
        except (TypeError, ValueError):
            state = None
    year = item.get("year")
    if isinstance(year, str):
        year = int(year) if year.isdigit() else None
    title_keys = _subscription_title_keys(item)
    candidate_types = [tmdb_type] if tmdb_type in {"movie", "tv"} else ["tv", "movie"]
    if not state:
        for media_type in candidate_types:
            for title_key in title_keys:
                state = by_identity.get((media_type, title_key, year)) or by_identity.get((media_type, title_key, None))
                if state:
                    tmdb_type = media_type
                    break
            if state:
                break
    if state:
        season, episode = _extract_item_episode(item)
        exact_state = _exact_existing_episode_state(state, season, episode)
        if episode and not exact_state:
            return item
        item["subscription_state"] = exact_state or state
        item["library_status"] = item["subscription_state"]["library_status"]
    return item


async def annotate_items_with_subscription_state(items: list[dict]) -> list[dict]:
    if not items:
        return items
    by_tmdb, by_identity = await get_subscription_state_maps()
    return [attach_subscription_state(item, by_tmdb, by_identity) for item in items]


def strip_live_state_from_results(payload: dict) -> dict:
    clean_payload = dict(payload)
    results = clean_payload.get("results")
    if isinstance(results, list):
        clean_results = []
        for item in results:
            if not isinstance(item, dict):
                clean_results.append(item)
                continue
            copy_item = dict(item)
            copy_item.pop("subscription_state", None)
            copy_item.pop("library_state", None)
            clean_results.append(copy_item)
        clean_payload["results"] = clean_results
    return clean_payload


def strip_live_state_from_items(payload: dict) -> dict:
    clean_payload = dict(payload)
    items = clean_payload.get("items")
    if isinstance(items, list):
        clean_items = []
        for item in items:
            if not isinstance(item, dict):
                clean_items.append(item)
                continue
            copy_item = dict(item)
            copy_item.pop("subscription_state", None)
            copy_item.pop("library_state", None)
            copy_item.pop("library_status", None)
            clean_items.append(copy_item)
        clean_payload["items"] = clean_items
    return clean_payload
