# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
import os
import sqlite3
import tempfile
import time

import cache_service
import poster_match_service
from config import DB_PATH
from poster_match_service import match_posters_for_messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark poster backfill matching with a temporary database.")
    parser.add_argument("--limit", type=int, default=50, help="number of target messages to copy and match")
    parser.add_argument("--concurrency", type=int, default=5, help="poster matching concurrency")
    parser.add_argument("--source-db", default=DB_PATH, help="source sqlite database path")
    parser.add_argument(
        "--copy-cache",
        action="store_true",
        help="copy poster_cache from the source database for a warm-cache benchmark",
    )
    parser.add_argument(
        "--skip-existing-posters",
        action="store_true",
        help="do not copy existing TMDB poster rows, forcing unresolved keys to call TMDB",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="keep the temporary benchmark database after the run",
    )
    return parser.parse_args()


def create_benchmark_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT,
            message_id INTEGER,
            title TEXT,
            description TEXT,
            language TEXT,
            type TEXT,
            actors TEXT,
            image_url TEXT,
            raw_text TEXT,
            publish_date TIMESTAMP,
            resource_url TEXT,
            tmdb_id INTEGER,
            tmdb_type TEXT,
            year INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE poster_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_messages_title ON messages(title)")
    conn.execute("CREATE INDEX idx_poster_cache_expires ON poster_cache(expires_at)")
    conn.commit()


def fetch_source_rows(source_db: str, limit: int) -> tuple[list[sqlite3.Row], list[sqlite3.Row], list[sqlite3.Row]]:
    source = sqlite3.connect(source_db)
    source.row_factory = sqlite3.Row
    try:
        target_rows = source.execute(
            """
            SELECT channel_name, message_id, title, description, language, type, actors,
                   raw_text, publish_date, resource_url, tmdb_id, tmdb_type, year
            FROM messages
            WHERE title IS NOT NULL AND title != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        existing_poster_rows = source.execute(
            """
            SELECT channel_name, message_id, title, description, language, type, actors,
                   image_url, raw_text, publish_date, resource_url, tmdb_id, tmdb_type, year
            FROM messages
            WHERE image_url LIKE 'https://image.tmdb.org/%'
              AND title IS NOT NULL
              AND title != ''
            """
        ).fetchall()

        cache_rows = source.execute(
            "SELECT cache_key, payload_json, expires_at, created_at FROM poster_cache"
        ).fetchall()
    finally:
        source.close()

    return target_rows, existing_poster_rows, cache_rows


def populate_benchmark_db(
    benchmark_db: str,
    target_rows: list[sqlite3.Row],
    existing_poster_rows: list[sqlite3.Row],
    cache_rows: list[sqlite3.Row],
    copy_cache: bool,
) -> list[int]:
    conn = sqlite3.connect(benchmark_db)
    try:
        create_benchmark_schema(conn)
        conn.executemany(
            """
            INSERT INTO messages (
                channel_name, message_id, title, description, language, type, actors,
                image_url, raw_text, publish_date, resource_url, tmdb_id, tmdb_type, year
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    row["channel_name"],
                    row["message_id"],
                    row["title"],
                    row["description"],
                    row["language"],
                    row["type"],
                    row["actors"],
                    row["image_url"],
                    row["raw_text"],
                    row["publish_date"],
                    row["resource_url"],
                    row["tmdb_id"],
                    row["tmdb_type"],
                    row["year"],
                )
                for row in existing_poster_rows
            ),
        )

        target_ids: list[int] = []
        for row in target_rows:
            cursor = conn.execute(
                """
                INSERT INTO messages (
                    channel_name, message_id, title, description, language, type, actors,
                    image_url, raw_text, publish_date, resource_url, tmdb_id, tmdb_type, year
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["channel_name"],
                    row["message_id"],
                    row["title"],
                    row["description"],
                    row["language"],
                    row["type"],
                    row["actors"],
                    row["raw_text"],
                    row["publish_date"],
                    row["resource_url"],
                    row["tmdb_id"],
                    row["tmdb_type"],
                    row["year"],
                ),
            )
            target_ids.append(cursor.lastrowid)

        if copy_cache:
            conn.executemany(
                """
                INSERT OR REPLACE INTO poster_cache (cache_key, payload_json, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ((row["cache_key"], row["payload_json"], row["expires_at"], row["created_at"]) for row in cache_rows),
            )

        conn.commit()
        return target_ids
    finally:
        conn.close()


def read_proxy_config(source_db: str) -> dict | None:
    conn = sqlite3.connect(source_db)
    try:
        row = conn.execute("SELECT value FROM config WHERE key = 'proxy'").fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    if not row:
        return None
    try:
        config = json.loads(row[0])
    except Exception:
        return None
    if not config.get("enabled", True) or config.get("mode") == "direct":
        return None
    return config


def count_updated_targets(benchmark_db: str, target_ids: list[int]) -> int:
    if not target_ids:
        return 0
    placeholders = ",".join("?" for _ in target_ids)
    conn = sqlite3.connect(benchmark_db)
    try:
        row = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM messages
            WHERE id IN ({placeholders})
              AND image_url LIKE 'https://image.tmdb.org/%'
            """,
            target_ids,
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


async def main() -> None:
    args = parse_args()
    source_db = os.path.abspath(args.source_db)
    if not os.path.exists(source_db):
        raise SystemExit(f"Source DB not found: {source_db}")

    target_rows, existing_poster_rows, cache_rows = fetch_source_rows(source_db, args.limit)
    if not target_rows:
        raise SystemExit("No source messages found.")

    temp_dir = tempfile.mkdtemp(prefix="poster-benchmark-")
    benchmark_db = os.path.join(temp_dir, "telegram_data.db")
    target_ids = populate_benchmark_db(
        benchmark_db,
        target_rows,
        [] if args.skip_existing_posters else existing_poster_rows,
        cache_rows,
        copy_cache=args.copy_cache,
    )

    poster_match_service.DB_PATH = benchmark_db
    cache_service.DB_PATH = benchmark_db

    proxy_config = read_proxy_config(source_db)
    started = time.perf_counter()
    stats = await match_posters_for_messages(
        target_ids,
        proxy_config=proxy_config,
        concurrency=args.concurrency,
    )
    elapsed_seconds = time.perf_counter() - started
    updated_targets = count_updated_targets(benchmark_db, target_ids)

    result = {
        "elapsed_seconds": round(elapsed_seconds, 3),
        "messages_per_second": round(len(target_ids) / elapsed_seconds, 3) if elapsed_seconds else None,
        "requested_limit": args.limit,
        "target_messages": len(target_ids),
        "existing_tmdb_rows_copied": 0 if args.skip_existing_posters else len(existing_poster_rows),
        "poster_cache_rows_copied": len(cache_rows) if args.copy_cache else 0,
        "copy_cache": args.copy_cache,
        "concurrency": args.concurrency,
        "updated_targets": updated_targets,
        "stats": stats,
        "benchmark_db": benchmark_db,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not args.keep_db:
        try:
            os.remove(benchmark_db)
            os.rmdir(temp_dir)
        except OSError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
