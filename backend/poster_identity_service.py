# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass


CHINESE_NUMBER_PATTERN = r"[一二两三四五六七八九十百\d]+"

@dataclass(frozen=True)
class MediaIdentity:
    key: str
    media_type: str | None
    tmdb_id: int | None
    clean_title: str
    year: int | None


def detect_media_type(title: str | None, raw_text: str | None = None) -> str | None:
    text = f"{title or ''}\n{raw_text or ''}"
    if re.search(r"(📺|电视剧|剧集|影集|番剧|连续剧)", text, re.IGNORECASE):
        return "tv"
    if re.search(r"(🎬|电影|影片|Movie)", text, re.IGNORECASE):
        return "movie"
    return None


def extract_tmdb_id(title: str | None, raw_text: str | None = None) -> int | None:
    text = f"{title or ''}\n{raw_text or ''}"
    patterns = [
        r"TMDB\s*(?:ID|id|Id)?\s*[:：#]?\s*(\d{2,10})",
        r"tmdb_id\s*[:：=]\s*(\d{2,10})",
        r"themoviedb\.org/(?:movie|tv)/(\d{2,10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def extract_year(title: str | None, raw_text: str | None = None) -> int | None:
    text = f"{title or ''}\n{raw_text or ''}"
    for pattern in (
        r"[\(（\[【]\s*((?:19|20)\d{2})(?:-\d{2}-\d{2})?\s*[\)）\]】]",
        r"(?<!\d)((?:19|20)\d{2})(?!\d)",
    ):
        for value in re.findall(pattern, text):
            year = int(value)
            if 1900 <= year <= 2100:
                return year
    return None


def clean_media_title(title: str | None, raw_text: str | None = None) -> str:
    source = (title or "").strip()
    if not source and raw_text:
        source = next((line.strip() for line in raw_text.splitlines() if line.strip()), "")

    year = extract_year(source)
    clean = source
    clean = re.sub(r"https?://\S+", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"TMDB\s*(?:ID|id|Id)?\s*[:：#]?\s*\d{2,10}", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"tmdb_id\s*[:：=]\s*\d{2,10}", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"themoviedb\.org/(?:movie|tv)/\d{2,10}", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[\[\]【】（）(){}<>《》]", " ", clean)

    if year:
        clean = re.sub(rf"(?<!\d){year}(?:-\d{{2}}-\d{{2}})?(?!\d)", " ", clean)

    noise_patterns = [
        r"更新至?\s*(?:第?\s*)?\d+\s*[集话期]?",
        r"更至?\s*(?:第?\s*)?\d+\s*[集话期]?",
        rf"第\s*{CHINESE_NUMBER_PATTERN}\s*[季集部话話期]",
        rf"(?:全|共)\s*{CHINESE_NUMBER_PATTERN}\s*[季集部话話期]",
        r"S\d{1,2}\s*E\d{1,4}",
        r"S\d{1,2}",
        r"E\d{1,4}",
        r"\b\d{1,2}x\d{1,4}\b",
        r"\b(?:4K|8K|2160P?|1080P?|720P?|480P?)\b",
        r"\b(?:WEB[-_. ]?DL|WEB[-_. ]?Rip|BluRay|BDRip|HDRip|HDTV|DVDRip|REMUX|HD|SD)\b",
        r"\b(?:HDR10\+?|HDR|HLG|SDR|DV|DoVi|Dolby\s*Vision|IMAX|60FPS|120FPS)\b",
        r"\b(?:HEVC|H\.?265|H\.?264|x265|x264|AVC|AV1|AAC|DTS|TrueHD|Atmos|DDP?5\.1|FLAC)\b",
        r"\b\d+(?:\.\d+)?\s*(?:GB|G|MB|TB|T)\b",
        r"中英双语|双语字幕|外挂字幕|内封字幕|官方字幕|中文字幕|简繁英字幕|字幕",
        r"杜比视界|杜比全景声|高码率|高画质|无水印|压制|修复版",
        r"电视剧|剧集|电影|影片|综艺|纪录片|动漫|动画|番剧",
        r"完结|已完结|连载中|连载|单集|合集",
    ]
    clean = re.sub("|".join(noise_patterns), " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[*_`~|/\\:;,.，。！!？?\"'“”‘’+-]+", " ", clean)
    clean = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def build_media_identity(
    title: str | None,
    raw_text: str | None = None,
    stored_tmdb_id: int | None = None,
    stored_tmdb_type: str | None = None,
    stored_year: int | None = None,
) -> MediaIdentity:
    media_type = stored_tmdb_type if stored_tmdb_type in {"movie", "tv"} else detect_media_type(title, raw_text)
    tmdb_id = stored_tmdb_id or extract_tmdb_id(title, raw_text)
    clean_title = clean_media_title(title, raw_text)
    year = stored_year or extract_year(title, raw_text)

    if tmdb_id:
        key_type = media_type or "unknown"
        return MediaIdentity(
            key=f"tmdb:{key_type}:{tmdb_id}",
            media_type=media_type,
            tmdb_id=tmdb_id,
            clean_title=clean_title,
            year=year,
        )

    key_type = media_type or "unknown"
    key_title = clean_title.lower()
    key = f"title:{key_type}:{key_title}:{year or ''}"
    return MediaIdentity(key=key, media_type=media_type, tmdb_id=None, clean_title=clean_title, year=year)
