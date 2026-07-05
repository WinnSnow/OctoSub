# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass
from typing import Optional

import PTN

from media_identity_service import coerce_media_number


CHINESE_NUMBER_PATTERN = r"[一二两三四五六七八九十百\d]+"

POSTER_TITLE_BLACKLIST = [
    r"动漫", r"电影", r"剧集", r"电视剧", r"综艺", r"纪录片", r"动画",
    r"中英双语", r"双语字幕", r"外挂字幕", r"内封字幕", r"官方字幕", r"中文字幕",
    r"杜比视界", r"杜比全景声", r"高码率", r"高画质",
    r"4K", r"1080P", r"2160P", r"720P", r"HDR10\+", r"HDR", r"SDR", r"DV",
    r"HEVC", r"x265", r"x264", r"AAC", r"REMUX", r"WEB-DL",
    r"完结", r"连载", r"连载中", r"已完结", r"单集", r"合集",
    r"BluRay", r"IMAX", r"60FPS",
]


@dataclass(frozen=True)
class PosterSearchIdentity:
    title: str
    year: Optional[int]
    source: str
    cleaned_input: str


@dataclass(frozen=True)
class PosterSearchQuery:
    title: str
    year: Optional[int]
    strategy: str


def extract_bracketed_year(title: str) -> Optional[int]:
    date_matches = re.findall(r"[\(（\[【](\d{4})-\d{2}-\d{2}[\)）\]】]", title)
    if date_matches:
        return int(date_matches[0])

    year_matches = re.findall(r"[\(（\[【](\d{4})[\)）\]】]", title)
    for year_match in year_matches:
        year = int(year_match)
        if 1900 <= year <= 2100:
            return year
    return None


def clean_poster_title_input(movie_title: str) -> str:
    clean = re.sub(r"[\(（\[【].*?[\)）\]】]", "", movie_title)
    clean = re.sub("|".join(POSTER_TITLE_BLACKLIST), "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(更新|更)至?\s*S?\d+.*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(rf"第\s*{CHINESE_NUMBER_PATTERN}\s*[季部集话話期]", "", clean)
    clean = re.sub(rf"(?:全|共)\s*{CHINESE_NUMBER_PATTERN}\s*[季部集话話期]", "", clean)
    clean = re.sub(r"S\d+E\d+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\d+(\.\d+)?\s*[kmgt]b?", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\*\*", "", clean)
    clean = re.sub(r"[^\w\s\u4e00-\u9fa5]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def trim_trailing_noise_number(clean_title: str, extracted_year: Optional[int]) -> str:
    match_end_digit = re.search(r"(\d+)$", clean_title)
    if match_end_digit:
        num = int(match_end_digit.group(1))
        if not (1900 <= num <= 2100) or (extracted_year and abs(num - extracted_year) > 5):
            clean_title = clean_title[:match_end_digit.start()].strip()
    return re.sub(r"\b\d{1,3}\b", "", clean_title).strip()


def parse_poster_search_identity(movie_title: str) -> PosterSearchIdentity:
    extracted_year = extract_bracketed_year(movie_title)
    cleaned_input = trim_trailing_noise_number(clean_poster_title_input(movie_title), extracted_year)

    ptn_title = ""
    ptn_year = None
    try:
        info = PTN.parse(cleaned_input)
        ptn_title = (info.get("title") or "").strip()
        ptn_year = coerce_media_number(info.get("year"))
    except Exception:
        ptn_title = ""
        ptn_year = None

    final_title = cleaned_input
    final_year = extracted_year
    source = "regex"
    if ptn_title and len(ptn_title) >= 2:
        final_title = ptn_title
        if not final_year and ptn_year:
            final_year = ptn_year
        source = "ptn"

    final_title = re.sub(r"[。，,！!\-]", " ", final_title).strip()
    return PosterSearchIdentity(
        title=final_title,
        year=final_year,
        source=source,
        cleaned_input=cleaned_input,
    )


def build_poster_search_queries(clean_title: str, year: Optional[int]) -> list[PosterSearchQuery]:
    queries = [PosterSearchQuery(clean_title, year, "primary")]

    if year:
        queries.append(PosterSearchQuery(clean_title, None, "ignore_year"))

    if " " in clean_title:
        simple_title = clean_title.split(" ")[0]
        if len(simple_title) >= 2:
            queries.append(PosterSearchQuery(simple_title, None, "simple_title"))

    no_bracket_title = re.sub(r"[\(（].*?[\)）]", "", clean_title).strip()
    if no_bracket_title != clean_title and len(no_bracket_title) >= 2:
        queries.append(PosterSearchQuery(no_bracket_title, None, "remove_brackets"))

    return queries
