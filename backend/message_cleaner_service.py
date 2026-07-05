# -*- coding: utf-8 -*-
"""Deterministic cleanup rules for noisy Telegram media posts.

This module is intentionally side-effect free.  It is used first by the
analysis script so rules can be audited against stored messages before they
are wired into the scraping path.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from urllib.parse import urlparse

from utils import hostname_matches


RESOURCE_DOMAINS = (
    "115.com",
    "115cdn.com",
    "anxia.com",
    "pan.quark.cn",
    "pan.baidu.com",
    "pan.xunlei.com",
    "hdhive.com",
    "hdhive.online",
    "alipan.com",
    "aliyundrive.com",
    "cloud.189.cn",
)

INTERMEDIATE_DOMAINS = (
    "telegra.ph",
    "graph.org",
    "pastebin.com",
    "justpaste.it",
)

AD_DOMAINS = (
    "hongxingyun6.vip",
    "candytally.cyou",
    "ultra.mooguu.net",
    "mooguu.net",
)

SOCIAL_DOMAINS = (
    "t.me",
    "telegram.me",
)

FOOTER_LINE_PATTERNS = (
    r"^\s*🤖?\s*投稿\s*[:：]",
    r"^\s*🙋\s*\*{0,2}投稿人\*{0,2}\s*[:：]",
    r"^\s*投稿人\s*[:：]",
    r"^\s*🔍\s*搜索\s*[:：]",
    r"^\s*✈️?\s*机场\s*[:：]",
    r"^\s*📺\s*公费服\s*[:：]",
    r"^\s*频道\s*[:：]",
    r"^\s*资源搜索机器人\s*bot\b",
    r"^\s*蘑菇.*Emby",
    r"^\s*群主自用机场\s*[:：]",
    r"^\s*VidHub\s*[:：]",
)

HARD_AD_PATTERNS = (
    r"TG必备搜索引擎",
    r"Telegram必备的搜索引擎",
    r"新币搜",
    r"极搜",
    r"JISOU",
    r"#频道互推",
    r"#群组推荐",
    r"#互推",
    r"高端嫩模",
    r"劳力士",
    r"奔驰E300",
    r"首存",
    r"日存彩金",
    r"爆奖",
    r"百家乐",
    r"娱乐城",
    r"全网广告费",
    r"免实名",
    r"无需绑银行卡",
    r"钱包WG",
    r"Y3国际",
    r"球速[·・]?体育",
    r"182\s*体育",
    r"2026世界杯",
)

MEDIA_EVIDENCE_PATTERNS = (
    r"(?:19|20)\d{2}",
    r"#(?:电影|剧集|电视剧|短剧|动漫|动画|番剧|纪录片|综艺)",
    r"\b(?:S\d{1,2}E\d{1,3}|EP?\d{1,3})\b",
    r"第\s*\d+\s*[集季]",
    r"(?:评分|类型|主演|导演|简介|剧情简介)\s*[:：]",
    r"\b(?:4K|8K|2160P?|1080P?|720P?|BluRay|WEB[-_. ]?DL|REMUX|HDR10?\+?|DoVi)\b",
)

INTERMEDIATE_SCORE_THRESHOLD = 3
INTERMEDIATE_STRUCTURED_LABELS = ("评分", "类型", "主演", "简介", "描述", "剧情简介")
INTERMEDIATE_TITLE_STRONG_RE = re.compile(
    r"(?:19|20)\d{2}|\bS\d{1,2}E\d{1,3}\b|第\s*\d+\s*[集季]",
    re.IGNORECASE,
)
INTERMEDIATE_MEDIA_TAG_RE = re.compile(r"#(?:电影|剧集|电视剧|合集|ed2k|磁力)", re.IGNORECASE)
INTERMEDIATE_QUALITY_RE = re.compile(
    r"\b(?:4K|8K|2160P?|1080P?|720P?|BluRay|WEB[-_. ]?DL|REMUX|HDR10?\+?|DoVi)\b",
    re.IGNORECASE,
)
INTERMEDIATE_CONTEXT_RE = re.compile(r"所属合集|包含影片|收录版本|链接")

URL_RE = re.compile(r"https?://[^\s<>\"]+|magnet:\?xt=[^\s<>\"]+|ed2k://[^\s<>\"]+", re.IGNORECASE)
TRAILING_URL_CHARS = "。。，，、；;！!？?）)]】》>\"'"


@dataclass(frozen=True)
class ClassifiedUrl:
    url: str
    kind: str
    domain: str | None = None


@dataclass(frozen=True)
class CleanMessageResult:
    original_text: str
    content_text: str
    removed_lines: tuple[str, ...]
    urls: tuple[ClassifiedUrl, ...]
    has_resource_url: bool
    has_intermediate_url: bool
    has_ad_url: bool
    has_media_evidence: bool
    hard_ad: bool
    intermediate_score: int
    intermediate_score_reasons: tuple[str, ...]
    should_keep: bool
    should_resolve_intermediate: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["urls"] = [asdict(url) for url in self.urls]
        return payload


def extract_urls(text: str | None) -> list[str]:
    if not text:
        return []
    urls = []
    for match in URL_RE.findall(text):
        cleaned = match.rstrip(TRAILING_URL_CHARS)
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


def classify_url(url: str) -> ClassifiedUrl:
    if url.lower().startswith("magnet:") or url.lower().startswith("ed2k://"):
        return ClassifiedUrl(url=url, kind="resource", domain=None)

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if hostname_matches(domain, RESOURCE_DOMAINS):
        kind = "resource"
    elif hostname_matches(domain, INTERMEDIATE_DOMAINS):
        kind = "intermediate"
    elif hostname_matches(domain, AD_DOMAINS):
        kind = "ad"
    elif hostname_matches(domain, SOCIAL_DOMAINS):
        kind = "social"
    else:
        kind = "other"
    return ClassifiedUrl(url=url, kind=kind, domain=domain or None)


def line_is_footer_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if any(re.search(pattern, stripped, re.IGNORECASE) for pattern in FOOTER_LINE_PATTERNS):
        return True

    urls = [classify_url(url) for url in extract_urls(stripped)]
    if urls and all(url.kind in {"ad", "social"} for url in urls):
        return True
    return False


def strip_footer_noise(text: str | None) -> tuple[str, tuple[str, ...]]:
    if not text:
        return "", ()

    kept_lines = []
    removed_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if line_is_footer_noise(stripped):
            removed_lines.append(stripped)
            continue
        kept_lines.append(stripped)
    return "\n".join(kept_lines), tuple(removed_lines)


def has_hard_ad_signal(text: str) -> bool:
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in HARD_AD_PATTERNS)


def has_media_evidence(text: str, title: str | None = None) -> bool:
    joined = "\n".join(part for part in (title or "", text or "") if part)
    if not joined:
        return False
    return any(re.search(pattern, joined, re.IGNORECASE) for pattern in MEDIA_EVIDENCE_PATTERNS)


def score_intermediate_candidate(title: str | None, content_text: str | None) -> tuple[int, tuple[str, ...]]:
    text = "\n".join(part for part in (title or "", content_text or "") if part)
    first_line = (content_text or "").split("\n", 1)[0] if content_text else ""
    score = 0
    reasons = []

    if INTERMEDIATE_TITLE_STRONG_RE.search(title or "") or INTERMEDIATE_TITLE_STRONG_RE.search(first_line):
        score += 2
        reasons.append("title_year_episode")

    label_count = sum(
        1
        for label in INTERMEDIATE_STRUCTURED_LABELS
        if re.search(label + r"\s*[:：]", text)
    )
    if label_count >= 2:
        score += 2
        reasons.append("structured_labels")

    if INTERMEDIATE_MEDIA_TAG_RE.search(text):
        score += 2
        reasons.append("media_tags")

    if INTERMEDIATE_QUALITY_RE.search(text):
        score += 1
        reasons.append("quality")

    if INTERMEDIATE_CONTEXT_RE.search(text):
        score += 1
        reasons.append("intermediate_context")

    return score, tuple(reasons)


def clean_message_text(
    *,
    title: str | None = None,
    raw_text: str | None = None,
    resource_url: str | None = None,
) -> CleanMessageResult:
    original_text = raw_text or ""
    content_text, removed_lines = strip_footer_noise(original_text)
    all_url_text = "\n".join(part for part in (title or "", content_text, resource_url or "") if part)
    urls = tuple(classify_url(url) for url in extract_urls(all_url_text))

    has_resource_url = any(item.kind == "resource" for item in urls)
    has_intermediate_url = any(item.kind == "intermediate" for item in urls)
    has_ad_url = any(item.kind == "ad" for item in urls)
    media_evidence = has_media_evidence(content_text, title)
    hard_ad = has_hard_ad_signal("\n".join(part for part in (title or "", content_text) if part))
    intermediate_score, intermediate_score_reasons = score_intermediate_candidate(title, content_text)

    reasons = []
    if removed_lines:
        reasons.append("footer_removed")
    if has_resource_url:
        reasons.append("resource_url")
    if has_intermediate_url:
        reasons.append("intermediate_url")
    if media_evidence:
        reasons.append("media_evidence")
    if hard_ad:
        reasons.append("hard_ad")
    if has_ad_url:
        reasons.append("ad_url_remaining")

    should_resolve_intermediate = bool(
        has_intermediate_url
        and not has_resource_url
        and not hard_ad
        and intermediate_score >= INTERMEDIATE_SCORE_THRESHOLD
    )
    should_keep = bool(
        has_resource_url
        or should_resolve_intermediate
        or (media_evidence and not hard_ad)
    )
    if should_resolve_intermediate:
        reasons.append("resolve_intermediate")
    if not should_keep:
        reasons.append("skip_no_media_resource")

    return CleanMessageResult(
        original_text=original_text,
        content_text=content_text,
        removed_lines=removed_lines,
        urls=urls,
        has_resource_url=has_resource_url,
        has_intermediate_url=has_intermediate_url,
        has_ad_url=has_ad_url,
        has_media_evidence=media_evidence,
        hard_ad=hard_ad,
        intermediate_score=intermediate_score,
        intermediate_score_reasons=intermediate_score_reasons,
        should_keep=should_keep,
        should_resolve_intermediate=should_resolve_intermediate,
        reasons=tuple(reasons),
    )
