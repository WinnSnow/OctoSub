# -*- coding: utf-8 -*-
"""Shared deterministic text rules for media candidate detection."""

MEDIA_KEYWORD_PATTERNS = (
    r"电影",
    r"影片",
    r"剧集",
    r"电视剧",
    r"番剧",
    r"动画",
    r"动漫",
    r"纪录片",
    r"综艺",
    r"短剧",
    r"Movie",
    r"TV",
    r"Season",
    r"Episode",
)

NEGATIVE_CONTENT_PATTERNS = (
    r"免费下载.*(?:音乐|歌曲|无损)",
    r"无损音乐",
    r"歌曲",
    r"音乐站",
    r"机场",
    r"加速器",
    r"VPN",
    r"海外专线",
    r"优惠码",
    r"开业.*优惠",
    r"套餐.*折",
    r"机器人.*(?:恢复|罢工|故障)",
    r"TG服务器",
    r"telegram.*api",
    r"频道互推",
    r"群组推荐",
    r"搜索引擎",
    r"快速搜索",
    r"新币搜",
    r"极搜",
    r"博彩",
    r"娱乐城",
    r"百家乐",
    r"首存",
    r"彩金",
    r"高端嫩模",
    r"劳力士",
    r"奔驰E300",
)

METADATA_LABEL_PATTERNS = (
    r"评分",
    r"类型",
    r"地区",
    r"语言",
    r"主演",
    r"简介",
    r"剧情简介",
    r"大小",
    r"标签",
    r"链接",
    r"投稿",
    r"资源",
    r"更新状态",
    r"上映时间",
    r"首播时间",
)

QUALITY_PATTERNS = {
    "4K": r"\b(?:4K|2160P?)\b",
    "1080p": r"\b1080P?\b",
    "720p": r"\b720P?\b",
    "REMUX": r"\bREMUX\b",
    "WEB-DL": r"\bWEB[-_. ]?DL\b",
    "BluRay": r"\bBluRay\b",
    "HDR": r"\b(?:HDR10\+?|HDR|DoVi|Dolby\s*Vision)\b",
}

TITLE_NOISE_PATTERNS = (
    r"https?://\S+",
    r"magnet:\?xt=\S+",
    r"ed2k://\S+",
    r"[\(（\[【]\s*(?:19|20)\d{2}(?:-\d{2}-\d{2})?\s*[\)）\]】]",
    r"\b(?:4K|8K|2160P?|1080P?|720P?|480P?)\b",
    r"\b(?:WEB[-_. ]?DL|WEB[-_. ]?Rip|BluRay|BDRip|HDRip|HDTV|DVDRip|REMUX|HD|SD)\b",
    r"\b(?:HDR10\+?|HDR|HLG|SDR|DV|DoVi|Dolby\s*Vision|IMAX|60FPS|120FPS)\b",
    r"\b(?:HEVC|H\.?265|H\.?264|x265|x264|AVC|AV1|AAC|DTS|TrueHD|Atmos|FLAC)\b",
    r"\b\d+(?:\.\d+)?\s*(?:GB|G|MB|TB|T)\b",
    r"中英双语|双语字幕|外挂字幕|内封字幕|官方字幕|中文字幕|简繁英字幕|字幕",
    r"完结|已完结|连载中|连载|单集",
)

RESOURCE_LINK_TYPES = {"115", "quark", "baidu", "aliyun", "magnet", "ed2k"}
