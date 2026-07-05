# -*- coding: utf-8 -*-
"""
媒体解析器
使用 PTN 库解析影视资源标题，提取季、集、质量等元数据
"""
from media_identity_service import coerce_media_number as coerce_media_number
from media_identity_service import generate_fingerprint as generate_fingerprint
from media_title_parse_service import (
    parse_and_generate_fingerprint as parse_and_generate_fingerprint,
)
from media_quality_service import match_quality_filter as match_quality_filter
from media_title_parse_service import (
    parse_media_title as parse_media_title,
)


__all__ = [
    "coerce_media_number",
    "generate_fingerprint",
    "match_quality_filter",
    "parse_and_generate_fingerprint",
    "parse_media_title",
]


# 测试函数
if __name__ == "__main__":
    # 测试用例
    test_titles = [
        "[字幕组] 庆余年2 S02E05 2160p H265 AAC.mp4",
        "庆余年.Joy.of.Life.2019.S01E01.1080p.WEB-DL.mp4",
        "流浪地球2.The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.AAC.mp4",
        "Avatar.The.Way.of.Water.2022.1080p.BluRay.x264.mp4",
        "Breaking.Bad.S05E16.FINAL.1080p.mp4"
    ]

    for title in test_titles:
        print(f"\n标题: {title}")
        parsed = parse_media_title(title)
        print(f"解析结果: {parsed}")
        fingerprint = generate_fingerprint(parsed)
        print(f"指纹: {fingerprint}")
