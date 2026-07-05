# -*- coding: utf-8 -*-
import re

from utils import normalize_text


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    value = re.sub(r"(?:链接|资源|分享)\s*[:：]?\s*$", "", value).strip()
    value = re.sub(r"[\(（\[{【]\s*$", "", value).strip()
    return value or "无标题"


def has_meaningful_title_text(value: str | None) -> bool:
    if not value:
        return False
    stripped = str(value).strip()
    if stripped in {"无标题", "无标题资源"}:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", stripped))


def looks_like_metadata_title(value: str | None) -> bool:
    return bool(re.match(
        r"^\s*(?:发行时间|上映时间|首播|首播时间|更新|更新状态|评分|类型|地区|语言|主演|简介|剧情简介|大小|标签)\s*[:：]",
        value or "",
    ))


def extract_labeled_title(value: str | None) -> str | None:
    match = re.match(r"^\s*(?:名称|片名|剧名|标题|资源名称)\s*[:：]\s*(.+?)\s*$", value or "")
    if not match:
        return None
    title = clean_title(match.group(1))
    return title if has_meaningful_title_text(title) else None


def looks_like_non_title_fragment(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    if looks_like_metadata_title(text):
        return True
    if re.fullmatch(r"[-–—_/\\.:：\s]*", text):
        return True
    if re.fullmatch(r"(?:19|20)\d{2}(?:[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?)?", text):
        return True
    if re.fullmatch(r"[-–—_/\\]\s*\d{1,2}(?:[-/月]\d{1,2}日?)?", text):
        return True
    return False


def extract_display_title(text: str | None, fallback: str = "无标题") -> str:
    if not text:
        return fallback
    ignored = {
        "评分", "类型", "地区", "语言", "主演", "简介", "链接", "投稿人",
        "大小", "标签", "资源", "点击跳转", "发行时间", "上映时间",
        "首播", "首播时间", "更新", "更新状态", "剧情简介",
    }
    for raw_line in str(text).splitlines():
        line = clean_title(raw_line)
        labeled_title = extract_labeled_title(line)
        if labeled_title:
            return labeled_title
        if not has_meaningful_title_text(line):
            continue
        if looks_like_non_title_fragment(line):
            continue
        if any(line.startswith(label) or line.startswith(f"{label}：") or line.startswith(f"{label}:") for label in ignored):
            continue
        return line
    compact = clean_title(text)
    labeled_title = extract_labeled_title(compact)
    if labeled_title:
        return labeled_title
    return compact if has_meaningful_title_text(compact) and not looks_like_non_title_fragment(compact) else fallback


def extract_result_display_title(payload: dict | None, fallback: str = "无标题资源") -> str:
    payload = payload or {}
    for key in ("title", "description", "raw_text", "content", "note"):
        value = payload.get(key)
        if has_meaningful_title_text(value):
            title = extract_display_title(value, fallback)
            if title != fallback and has_meaningful_title_text(title) and not looks_like_metadata_title(title):
                return title
    return fallback


def clean_media_identity_title(title: str | None) -> str:
    value = clean_title(title or "")
    value = re.sub(r"^[^\u4e00-\u9fffA-Za-z0-9]+", "", value).strip()
    value = re.sub(r"^(?:电影|电视剧|剧集|动漫|动画|资源)\s*[:：]\s*", "", value).strip()
    value = re.sub(r"[\[【（(].*$", "", value).strip()
    return clean_title(value)


def build_library_check_title(title: str | None) -> str:
    value = clean_media_identity_title(title)
    value = re.sub(r"[\s\-_:：·]*(?:19\d{2}|20\d{2})\s*$", "", value).strip()
    value = re.sub(
        r"\b(?:4k|8k|1080p|2160p|720p|hdr|dv|remux|web[-_. ]?dl|bluray|x26[45]|hevc|mkv|mp4)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    return clean_title(value)


def extract_episode_hint(title: str | None) -> tuple[int | None, int | None]:
    value = title or ""
    match = re.search(r"S(\d{1,2})\s*E(\d{1,4})", value, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"第\s*(\d{1,4})\s*[集话話]", value)
    if match:
        return 1, int(match.group(1))
    match = re.search(r"(?:更新至|更至|更)\s*(\d{1,4})", value)
    if match:
        return 1, int(match.group(1))
    match = re.search(r"(?<!\d)(\d{1,4})\s*[集话話](?!\d)", value)
    if match:
        return 1, int(match.group(1))
    return None, None


def normalize_subscription_key(title: str | None) -> str:
    return normalize_text(clean_media_identity_title(title or ""))
