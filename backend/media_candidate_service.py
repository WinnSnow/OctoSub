# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass
from typing import Iterable

from media_text_rules import (
    MEDIA_KEYWORD_PATTERNS,
    METADATA_LABEL_PATTERNS,
    NEGATIVE_CONTENT_PATTERNS,
    QUALITY_PATTERNS,
    RESOURCE_LINK_TYPES,
    TITLE_NOISE_PATTERNS,
)
from media_title_parse_service import parse_media_title
from title_utils import clean_title, extract_labeled_title, looks_like_non_title_fragment
from utils import classify_resource_url


@dataclass(frozen=True)
class MediaCandidate:
    is_media_candidate: bool
    confidence: float
    clean_title: str
    description: str
    media_type: str | None
    year: int | None
    season: int | None
    episode: int | None
    quality_tags: list[str]
    resource_links: list[str]
    primary_resource_url: str | None
    skip_reason: str | None
    allow_tmdb_lookup: bool
    allow_jellyfin_lookup: bool
    parser_source: str


def _pattern_found(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in patterns)


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _normalize_links(links: list[str] | None, raw_text: str | None = None) -> list[str]:
    values = list(links or [])
    if raw_text:
        values.extend(re.findall(r"https?://[^\s\"'<>）)】]+|magnet:\?xt=[^\s\"'<>）)】]+|ed2k://[^\s\"'<>）)】]+", raw_text))
    return _dedupe(url.rstrip(".,，。;；") for url in values)


def _resource_links(links: list[str]) -> list[str]:
    return [url for url in links if classify_resource_url(url) in RESOURCE_LINK_TYPES]


def extract_quality_tags(text: str) -> list[str]:
    return [label for label, pattern in QUALITY_PATTERNS.items() if re.search(pattern, text or "", re.IGNORECASE)]


def extract_year(text: str) -> int | None:
    for value in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text or ""):
        year = int(value)
        if 1900 <= year <= 2100:
            return year
    return None


def extract_season_episode(text: str) -> tuple[int | None, int | None]:
    value = text or ""
    match = re.search(r"\bS0?(\d{1,2})\s*E0?(\d{1,4})\b", value, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"第\s*(\d{1,2})\s*季.{0,12}?第\s*(\d{1,4})\s*[集话話]", value)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"第\s*(\d{1,4})\s*[集话話]", value)
    if match:
        return 1, int(match.group(1))
    match = re.search(r"(?:更新至|更至|更)\s*(\d{1,4})", value)
    if match:
        return 1, int(match.group(1))
    return None, None


def infer_media_type(text: str, season: int | None, episode: int | None) -> str | None:
    if season or episode or re.search(r"(📺|电视剧|剧集|影集|番剧|连续剧|S\d{1,2}E\d{1,4})", text or "", re.IGNORECASE):
        return "tv"
    if re.search(r"(🎬|电影|影片|Movie)", text or "", re.IGNORECASE):
        return "movie"
    return None


def _clean_line(line: str) -> str:
    value = line.strip()
    labeled = extract_labeled_title(value)
    if labeled:
        value = labeled
    for pattern in TITLE_NOISE_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"^[#*_`~|/\\:;,.，。！!？?\"'“”‘’+\-\s]+", "", value)
    value = re.sub(r"^[^\u4e00-\u9fffA-Za-z0-9]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return clean_title(value)


def select_title_line(raw_text: str | None) -> str:
    text = raw_text or ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.search(r"https?://|magnet:\?|ed2k://", line, re.IGNORECASE):
            continue
        if re.match(rf"^\s*(?:{'|'.join(METADATA_LABEL_PATTERNS)})\s*[:：]", line):
            continue
        cleaned = _clean_line(line)
        if cleaned and not looks_like_non_title_fragment(cleaned):
            return cleaned
    return _clean_line(text)


def _looks_like_long_notice(title: str, text: str) -> bool:
    compact = re.sub(r"\s+", "", title or "")
    if len(compact) < 36:
        return False
    has_media_shape = bool(
        re.search(r"S\d{1,2}E\d{1,4}|第\s*\d+\s*[季集话話]|(?:19|20)\d{2}|\b(?:4K|1080P?|2160P?)\b", text or "", re.IGNORECASE)
    )
    return not has_media_shape


def analyze_media_candidate(
    *,
    title: str | None = None,
    raw_text: str | None = None,
    links: list[str] | None = None,
    fallback_parser_fn=parse_media_title,
) -> MediaCandidate:
    text = "\n".join(part for part in (title or "", raw_text or "") if part)
    all_links = _normalize_links(links, text)
    resource_links = _resource_links(all_links)
    source_title = title or select_title_line(raw_text)
    clean = _clean_line(source_title)

    negative = _pattern_found(NEGATIVE_CONTENT_PATTERNS, text)
    media_keyword = _pattern_found(MEDIA_KEYWORD_PATTERNS, text)
    year = extract_year(text)
    season, episode = extract_season_episode(text)
    quality_tags = extract_quality_tags(text)
    media_type = infer_media_type(text, season, episode)
    parser_source = "rules"

    parser_allowed = (
        bool(clean)
        and not negative
        and not _looks_like_long_notice(clean, text)
        and bool(resource_links or media_keyword or year or season or episode or quality_tags)
    )
    if parser_allowed and fallback_parser_fn:
        try:
            parsed = fallback_parser_fn(clean)
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            parser_source = "rules+ptn"
            year = year or parsed.get("year")
            season = season or parsed.get("season")
            episode = episode or parsed.get("episode")
            if not media_type and parsed.get("type") == "episode":
                media_type = "tv"

    confidence = 0.0
    if resource_links:
        confidence += 0.35
    if media_keyword:
        confidence += 0.2
    if year:
        confidence += 0.12
    if season or episode:
        confidence += 0.18
    if quality_tags:
        confidence += 0.15
    if re.search(r"评分\s*[:：]|简介\s*[:：]", text):
        confidence += 0.12
    if clean and len(clean) >= 2:
        confidence += 0.08

    skip_reason = None
    if negative and not (resource_links and (media_keyword or year or quality_tags or season or episode)):
        skip_reason = "negative_content"
    elif _looks_like_long_notice(clean, text) and not resource_links:
        skip_reason = "long_notice"
    elif not clean or clean == "无标题":
        skip_reason = "empty_title"
    elif confidence < 0.38:
        skip_reason = "low_confidence"

    is_media = skip_reason is None
    allow_tmdb = is_media and confidence >= 0.45 and not negative
    allow_jellyfin = is_media and confidence >= 0.5 and not negative and bool(year or season or episode or media_type)

    return MediaCandidate(
        is_media_candidate=is_media,
        confidence=round(min(confidence, 0.98), 2),
        clean_title=clean if is_media else "",
        description="",
        media_type=media_type,
        year=year,
        season=season,
        episode=episode,
        quality_tags=quality_tags,
        resource_links=resource_links,
        primary_resource_url=resource_links[0] if resource_links else None,
        skip_reason=skip_reason,
        allow_tmdb_lookup=allow_tmdb,
        allow_jellyfin_lookup=allow_jellyfin,
        parser_source=parser_source,
    )
