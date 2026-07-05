# -*- coding: utf-8 -*-
"""Audit cleaner rules against stored Telegram messages.

Examples:
    python analyze_message_cleaner.py
    python analyze_message_cleaner.py --limit 500 --show-skipped 10
    python analyze_message_cleaner.py --channel Lsp115 --jsonl-output /tmp/cleaner.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter, defaultdict

from config import DB_PATH
from message_cleaner_service import clean_message_text


def connect_readonly(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise SystemExit(f"数据库不存在: {db_path}")
    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_channels(conn: sqlite3.Connection, selected_channels: list[str]) -> list[sqlite3.Row]:
    if selected_channels:
        placeholders = ",".join("?" for _ in selected_channels)
        return conn.execute(
            f"""
            SELECT channel_name, COUNT(*) AS total
            FROM messages
            WHERE channel_name IN ({placeholders})
            GROUP BY channel_name
            ORDER BY total DESC, channel_name
            """,
            selected_channels,
        ).fetchall()

    return conn.execute("""
        SELECT channel_name, COUNT(*) AS total
        FROM messages
        WHERE channel_name IS NOT NULL AND channel_name != ''
        GROUP BY channel_name
        ORDER BY total DESC, channel_name
    """).fetchall()


def fetch_channel_messages(conn: sqlite3.Connection, channel_name: str, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, channel_name, message_id, title, raw_text, resource_url, publish_date
        FROM messages
        WHERE channel_name = ?
        ORDER BY publish_date DESC, id DESC
        LIMIT ?
        """,
        (channel_name, limit),
    ).fetchall()


def row_summary(row: sqlite3.Row, result) -> dict:
    return {
        "id": row["id"],
        "channel_name": row["channel_name"],
        "message_id": row["message_id"],
        "publish_date": row["publish_date"],
        "title": row["title"],
        "should_keep": result.should_keep,
        "should_resolve_intermediate": result.should_resolve_intermediate,
        "reasons": list(result.reasons),
        "removed_lines": list(result.removed_lines),
        "urls": [url.__dict__ for url in result.urls],
        "content_preview": result.content_text[:500],
    }


def print_sample(title: str, samples: list[dict], limit: int) -> None:
    if not samples or limit <= 0:
        return
    print(f"\n{title}:")
    for sample in samples[:limit]:
        print(
            f"  - #{sample['id']} {sample['channel_name']} msg={sample['message_id']} "
            f"keep={sample['should_keep']} reasons={','.join(sample['reasons'])}"
        )
        if sample["title"]:
            print(f"    title: {sample['title']}")
        preview = " ".join((sample["content_preview"] or "").split())
        if preview:
            print(f"    content: {preview[:180]}")
        removed = sample["removed_lines"][:3]
        if removed:
            print(f"    removed: {' | '.join(removed)}")


def analyze(args: argparse.Namespace) -> int:
    totals = Counter()
    per_channel: dict[str, Counter] = defaultdict(Counter)
    skipped_samples = []
    suspicious_samples = []
    low_signal_kept_samples = []

    jsonl_file = open(args.jsonl_output, "w", encoding="utf-8") if args.jsonl_output else None
    try:
        with connect_readonly(args.db_path) as conn:
            channels = fetch_channels(conn, args.channel)
            if not channels:
                print("没有找到可分析的频道。")
                return 1

            print(f"数据库: {args.db_path}")
            print(f"每频道样本上限: {args.limit}")
            print("")
            print("频道汇总:")

            for channel in channels:
                channel_name = channel["channel_name"]
                rows = fetch_channel_messages(conn, channel_name, args.limit)
                for row in rows:
                    result = clean_message_text(
                        title=row["title"],
                        raw_text=row["raw_text"],
                        resource_url=row["resource_url"],
                    )
                    summary = row_summary(row, result)
                    if jsonl_file:
                        jsonl_file.write(json.dumps(summary, ensure_ascii=False) + "\n")

                    counters = per_channel[channel_name]
                    counters["total"] += 1
                    counters["keep" if result.should_keep else "skip"] += 1
                    counters["footer_removed"] += int(bool(result.removed_lines))
                    counters["hard_ad"] += int(result.hard_ad)
                    counters["resource_url"] += int(result.has_resource_url)
                    counters["intermediate_url"] += int(result.has_intermediate_url)
                    counters["resolve_intermediate"] += int(result.should_resolve_intermediate)
                    counters["ad_url_remaining"] += int(result.has_ad_url)

                    if not result.should_keep:
                        skipped_samples.append(summary)
                    if not result.should_keep and result.has_resource_url:
                        suspicious_samples.append(summary)
                    if result.should_keep and result.has_resource_url and not result.has_media_evidence:
                        low_signal_kept_samples.append(summary)

                totals.update(per_channel[channel_name])
                counters = per_channel[channel_name]
                print(
                    f"  {channel_name}: 样本 {counters['total']}/{channel['total']}，"
                    f"保留 {counters['keep']}，过滤 {counters['skip']}，"
                    f"页脚清洗 {counters['footer_removed']}，硬广告 {counters['hard_ad']}，"
                    f"资源 {counters['resource_url']}，中转 {counters['intermediate_url']}，"
                    f"允许中转 {counters['resolve_intermediate']}"
                )

        print("")
        print(
            "总计: "
            f"样本 {totals['total']}，保留 {totals['keep']}，过滤 {totals['skip']}，"
            f"页脚清洗 {totals['footer_removed']}，硬广告 {totals['hard_ad']}，"
            f"资源 {totals['resource_url']}，中转 {totals['intermediate_url']}，"
            f"允许中转 {totals['resolve_intermediate']}，"
            f"资源误杀候选 {len(suspicious_samples)}"
        )

        print_sample("被过滤样本", skipped_samples, args.show_skipped)
        print_sample("资源误杀候选", suspicious_samples, args.show_suspicious)
        print_sample("低影视信号但因资源保留样本", low_signal_kept_samples, args.show_low_signal)

        if args.jsonl_output:
            print(f"\n明细已写入: {args.jsonl_output}")
        return 0
    finally:
        if jsonl_file:
            jsonl_file.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读评估 Telegram 消息 cleaner 规则")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--limit", type=int, default=200, help="每个频道抽样条数")
    parser.add_argument("--channel", action="append", default=[], help="只分析指定频道，可重复传入")
    parser.add_argument("--show-skipped", type=int, default=5, help="展示被过滤样本数量")
    parser.add_argument("--show-suspicious", type=int, default=10, help="展示资源误杀候选数量")
    parser.add_argument("--show-low-signal", type=int, default=5, help="展示低影视信号但保留样本数量")
    parser.add_argument("--jsonl-output", help="输出逐条明细 JSONL")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(analyze(parse_args()))
