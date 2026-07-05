# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass
from typing import Any

from media_candidate_service import analyze_media_candidate
from media_parser import coerce_media_number, parse_media_title
from title_utils import (
    build_library_check_title,
    extract_display_title,
    extract_episode_hint,
    has_meaningful_title_text,
    looks_like_metadata_title,
    looks_like_non_title_fragment,
)
from utils import normalize_text


@dataclass(frozen=True)
class LibraryStateRequest:
    key: str | None
    cache_key: str
    check_title: str
    media_type: str
    tmdb_id: int | None
    year: int | None
    season: int | None
    episode: int | None
    progress_current: int
    progress_total: int


def valid_library_title(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"评分", "类型", "大小", "地区", "语言", "主演", "简介", "剧情简介", "标签"}:
        return None
    if not has_meaningful_title_text(text):
        return None
    if looks_like_metadata_title(text) or looks_like_non_title_fragment(text):
        return None
    extracted = extract_display_title(text, "")
    if extracted in {"评分", "类型", "大小", "地区", "语言", "主演", "简介", "剧情简介", "标签"}:
        return None
    if not extracted or looks_like_metadata_title(extracted) or looks_like_non_title_fragment(extracted):
        return None
    return extracted


def extract_library_title(item: dict) -> str | None:
    for key in ("title", "library_check_title", "subscription_keyword", "search_keyword", "name"):
        title = valid_library_title(item.get(key))
        if title:
            return title

    for key in ("description", "raw_text", "content", "note"):
        title = valid_library_title(item.get(key))
        if title:
            return title
    return None


def coerce_year(value: Any) -> int | None:
    year = coerce_media_number(value)
    if year and 1900 <= year <= 2100:
        return year
    return None


def coerce_tmdb_id(value: Any) -> int | None:
    tmdb_id = coerce_media_number(value)
    if tmdb_id and tmdb_id > 0:
        return tmdb_id
    return None


def text_parts(item: dict, display_title: str | None = None) -> list[str]:
    parts = []
    if display_title:
        parts.append(display_title)
    for key in ("title", "raw_text", "description", "content", "note", "type"):
        value = item.get(key)
        if value is not None:
            parts.append(str(value))
    return parts


def extract_text_year(parts: list[str]) -> int | None:
    text = "\n".join(parts)
    for pattern in (
        r"[\(（\[【]\s*((?:19|20)\d{2})(?:-\d{2}-\d{2})?\s*[\)）\]】]",
        r"(?<!\d)((?:19|20)\d{2})(?!\d)",
    ):
        for value in re.findall(pattern, text):
            year = coerce_year(value)
            if year:
                return year
    return None


def extract_text_tmdb_id(parts: list[str]) -> int | None:
    text = "\n".join(parts)
    for pattern in (
        r"TMDB\s*(?:ID|id|Id)?\s*[:：#]?\s*(\d{2,10})",
        r"tmdb_id\s*[:：=]\s*(\d{2,10})",
        r"themoviedb\.org/(?:movie|tv)/(\d{2,10})",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def infer_media_type_from_text(parts: list[str]) -> str | None:
    text = "\n".join(parts)
    if re.search(r"(📺|#\s*剧集|电视剧|剧集|影集|番剧|连续剧|更新至\s*\d+\s*[集话話]?|更至\s*\d+\s*[集话話]?|S\d{1,2}\s*E\d{1,4})", text, re.IGNORECASE):
        return "tv"
    if re.search(r"(🎬|#\s*电影|电影|影片|Movie)", text, re.IGNORECASE):
        return "movie"
    return None


def build_library_state_request(item: dict, index: int) -> LibraryStateRequest | None:
    if not isinstance(item, dict):
        return None

    display_title = extract_library_title(item)
    if not display_title:
        return None

    parsed = parse_media_title(display_title)
    parts = text_parts(item, display_title)
    candidate = analyze_media_candidate(title=display_title, raw_text="\n".join(parts))
    year = coerce_year(item.get("year")) or coerce_year(parsed.get("year")) or extract_text_year(parts)
    year = year or candidate.year
    tmdb_id = coerce_tmdb_id(item.get("tmdb_id")) or extract_text_tmdb_id(parts)

    subscription_state = item.get("subscription_state") if isinstance(item.get("subscription_state"), dict) else {}
    progress_current = coerce_media_number(subscription_state.get("progress_current")) or 0
    progress_total = coerce_media_number(subscription_state.get("progress_total")) or 0

    explicit_media_type = item.get("tmdb_type") or item.get("media_type")
    media_type = explicit_media_type if explicit_media_type in {"movie", "tv"} else None
    if media_type is None:
        inferred_media_type = infer_media_type_from_text(parts)
        media_type = "tv" if progress_total or parsed.get("type") == "episode" or inferred_media_type == "tv" or candidate.media_type == "tv" else (candidate.media_type or inferred_media_type or "movie")

    season = coerce_media_number(item.get("season")) or coerce_media_number(parsed.get("season"))
    episode = coerce_media_number(item.get("episode")) or coerce_media_number(parsed.get("episode"))
    hint_season, hint_episode = extract_episode_hint(display_title)
    progress_hint_text = "\n".join(parts)
    has_progress_hint = bool(re.search(r"(?:更新至|更至|更)\s*\d{1,4}", progress_hint_text))
    season = season or hint_season or (None if has_progress_hint else candidate.season)
    episode = episode or hint_episode or (None if has_progress_hint else candidate.episode)

    structured_signal = bool(
        tmdb_id
        or (explicit_media_type in {"movie", "tv"} and (year or season or episode or progress_total))
        or (media_type == "tv" and (season or episode or progress_total))
    )
    if not structured_signal and not candidate.allow_jellyfin_lookup:
        return None

    if media_type == "movie":
        check_source = item.get("library_check_title") or parsed.get("title") or display_title
    else:
        check_source = (
            subscription_state.get("title")
            or item.get("subscription_keyword")
            or item.get("library_check_title")
            or parsed.get("title")
            or display_title
        )
    check_title = build_library_check_title(check_source)
    if not valid_library_title(check_title):
        return None

    normalized = normalize_text(check_title)
    if not normalized:
        return None

    cache_key = "|".join([
        media_type,
        str(tmdb_id or ""),
        normalized,
        str(year or ""),
        str(season or ""),
        str(episode or ""),
    ])
    return LibraryStateRequest(
        key=str(item.get("key")) if item.get("key") is not None else str(index),
        cache_key=cache_key,
        check_title=check_title,
        media_type=media_type,
        tmdb_id=tmdb_id,
        year=year,
        season=season,
        episode=episode,
        progress_current=progress_current,
        progress_total=progress_total,
    )
