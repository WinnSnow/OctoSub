# -*- coding: utf-8 -*-
import json
import re
import asyncio
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

import aiosqlite

from config import DB_PATH, JELLYFIN_LIBRARY_INDEX_REFRESH_MIN_INTERVAL_SECONDS
from db import connect_db
from library_state_query_service import state_payload
from library_state_request_service import LibraryStateRequest
from media_parser import coerce_media_number
from structured_logging import log_event
from title_utils import build_library_check_title, normalize_subscription_key


def _provider_tmdb_id(item: dict) -> int | None:
    provider_ids = item.get("ProviderIds") if isinstance(item.get("ProviderIds"), dict) else {}
    for key in ("Tmdb", "TMDB", "TheMovieDb"):
        tmdb_id = coerce_media_number(provider_ids.get(key))
        if tmdb_id:
            return int(tmdb_id)
    return None


def _media_type(item: dict) -> str | None:
    item_type = item.get("Type")
    if item_type == "Movie":
        return "movie"
    if item_type == "Series":
        return "series"
    if item_type == "Episode":
        return "episode"
    return None


def _normalized_title(value: str | None) -> str:
    return normalize_subscription_key(build_library_check_title(value or ""))


def _strip_episode_noise(value: str | None) -> str:
    text = value or ""
    text = re.sub(r"\bS\d{1,2}\s*E\d{1,4}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:更新至|更至|更)\s*\d{1,4}\s*[集话話]?", " ", text)
    text = re.sub(r"第\s*\d{1,4}\s*[集话話]", " ", text)
    text = re.sub(r"(?<!\d)\d{1,4}\s*[集话話](?!\d)", " ", text)
    return build_library_check_title(re.sub(r"\s+", " ", text).strip())


def _request_title_keys(request: LibraryStateRequest) -> list[str]:
    values = [
        request.check_title,
        _strip_episode_noise(request.check_title),
    ]
    keys = [_normalized_title(value) for value in values if value]
    return list(dict.fromkeys(key for key in keys if key))


def _row_from_item(item: dict) -> tuple | None:
    media_type = _media_type(item)
    jellyfin_id = item.get("Id")
    if not media_type or not jellyfin_id:
        return None

    title = item.get("Name") or item.get("OriginalTitle") or item.get("SortName")
    series_title = item.get("SeriesName") if media_type == "episode" else (title if media_type == "series" else None)
    return (
        str(jellyfin_id),
        item.get("SeriesId") if media_type == "episode" else None,
        media_type,
        title,
        _normalized_title(title),
        series_title,
        _normalized_title(series_title),
        coerce_media_number(item.get("ProductionYear")),
        _provider_tmdb_id(item),
        coerce_media_number(item.get("ParentIndexNumber")) if media_type == "episode" else None,
        coerce_media_number(item.get("IndexNumber")) if media_type == "episode" else None,
        json.dumps(item, ensure_ascii=False, separators=(",", ":")),
    )


async def sync_jellyfin_library_index(
    jellyfin,
    *,
    db_path: str = DB_PATH,
    update_progress: Callable[..., None] | None = None,
) -> dict:
    if not jellyfin:
        raise RuntimeError("Jellyfin 未配置")
    items = await jellyfin.get_library_items()
    rows = [row for row in (_row_from_item(item) for item in items) if row]
    if not rows:
        raise RuntimeError("未获取到 Jellyfin 媒体项，已保留现有索引")
    counts = Counter(row[2] for row in rows)

    if update_progress:
        update_progress(current=0, total=len(rows), message=f"获取到 {len(rows)} 个 Jellyfin 媒体项，正在写入索引")

    async with connect_db(db_path, timeout=60.0) as conn:
        await conn.execute("DELETE FROM jellyfin_library_items")
        if rows:
            await conn.executemany(
                """
                INSERT OR REPLACE INTO jellyfin_library_items (
                    jellyfin_id, series_jellyfin_id, media_type, title, normalized_title,
                    series_title, normalized_series_title, year, tmdb_id, season, episode,
                    payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                rows,
            )
        await conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            ("jellyfin_library_index_last_sync_count", str(len(rows))),
        )
        await conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("jellyfin_library_index_last_sync_at",),
        )
        await conn.commit()

    return {
        "total": len(rows),
        "movies": counts.get("movie", 0),
        "series": counts.get("series", 0),
        "episodes": counts.get("episode", 0),
    }


async def get_jellyfin_library_index_summary(*, db_path: str = DB_PATH) -> dict:
    try:
        async with connect_db(db_path, row_factory=aiosqlite.Row) as conn:
            async with conn.execute(
                "SELECT media_type, COUNT(*) AS count FROM jellyfin_library_items GROUP BY media_type"
            ) as cursor:
                counts = {row["media_type"]: row["count"] for row in await cursor.fetchall()}
            async with conn.execute(
                "SELECT value, updated_at FROM system_config WHERE key = 'jellyfin_library_index_last_sync_at'"
            ) as cursor:
                sync_row = await cursor.fetchone()
    except aiosqlite.Error:
        return {"available": False, "schema_ready": False, "total": 0, "movies": 0, "series": 0, "episodes": 0, "last_sync_at": None}

    total = sum(int(value or 0) for value in counts.values())
    return {
        "available": total > 0,
        "schema_ready": True,
        "total": total,
        "movies": counts.get("movie", 0),
        "series": counts.get("series", 0),
        "episodes": counts.get("episode", 0),
        "last_sync_at": sync_row["value"] if sync_row else None,
    }


async def has_jellyfin_library_index(*, db_path: str = DB_PATH) -> bool:
    return bool((await get_jellyfin_library_index_summary(db_path=db_path)).get("available"))


def _parse_sync_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def refresh_jellyfin_library_index_if_stale(
    *,
    reason: str,
    min_interval_seconds: int = JELLYFIN_LIBRARY_INDEX_REFRESH_MIN_INTERVAL_SECONDS,
    force: bool = False,
    db_path: str = DB_PATH,
) -> dict:
    summary = await get_jellyfin_library_index_summary(db_path=db_path)
    if not summary.get("schema_ready", True):
        return {"refreshed": False, "reason": reason, "skipped": "schema_not_ready"}
    last_sync = _parse_sync_time(summary.get("last_sync_at"))
    now = datetime.now(timezone.utc)
    if not force and last_sync and (now - last_sync).total_seconds() < min_interval_seconds:
        return {
            "refreshed": False,
            "reason": reason,
            "skipped": "recent_sync",
            "last_sync_at": summary.get("last_sync_at"),
        }

    from jellyfin_service import ensure_jellyfin_client

    jellyfin = await ensure_jellyfin_client()
    if not jellyfin:
        return {"refreshed": False, "reason": reason, "skipped": "jellyfin_not_configured"}

    result = await sync_jellyfin_library_index(jellyfin, db_path=db_path)
    return {"refreshed": True, "reason": reason, **result}


async def _safe_refresh_jellyfin_library_index(reason: str) -> None:
    try:
        result = await refresh_jellyfin_library_index_if_stale(reason=reason)
        if result.get("refreshed"):
            log_event("jellyfin.library_index.refreshed", **result)
        elif result.get("skipped"):
            log_event("jellyfin.library_index.skipped", **result)
    except Exception as exc:
        log_event("jellyfin.library_index.refresh_failed", "warning", reason=reason, error=str(exc))


def schedule_jellyfin_library_index_refresh(reason: str) -> None:
    try:
        asyncio.get_running_loop().create_task(_safe_refresh_jellyfin_library_index(reason))
    except RuntimeError:
        asyncio.run(_safe_refresh_jellyfin_library_index(reason))


async def _fetch_one(conn: aiosqlite.Connection, sql: str, params: tuple) -> dict | None:
    async with conn.execute(sql, params) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def _movie_state(conn: aiosqlite.Connection, request: LibraryStateRequest) -> dict | None:
    if request.tmdb_id:
        row = await _fetch_one(
            conn,
            "SELECT * FROM jellyfin_library_items WHERE media_type = 'movie' AND tmdb_id = ? LIMIT 1",
            (request.tmdb_id,),
        )
        if row:
            return {**state_payload("completed", "已入库", 1, 1), "source": "jellyfin_index"}

    for title_key in _request_title_keys(request):
        params: tuple
        if request.year:
            sql = """
                SELECT *
                FROM jellyfin_library_items
                WHERE media_type = 'movie'
                  AND normalized_title = ?
                  AND (year = ? OR year IS NULL)
                ORDER BY CASE WHEN year = ? THEN 0 ELSE 1 END
                LIMIT 1
            """
            params = (title_key, request.year, request.year)
        else:
            sql = """
                SELECT *
                FROM jellyfin_library_items
                WHERE media_type = 'movie' AND normalized_title = ?
                LIMIT 1
            """
            params = (title_key,)
        row = await _fetch_one(conn, sql, params)
        if row:
            return {**state_payload("completed", "已入库", 1, 1), "source": "jellyfin_index"}
    return None


async def _series_id_for_tmdb(conn: aiosqlite.Connection, tmdb_id: int | None) -> str | None:
    if not tmdb_id:
        return None
    row = await _fetch_one(
        conn,
        "SELECT jellyfin_id FROM jellyfin_library_items WHERE media_type = 'series' AND tmdb_id = ? LIMIT 1",
        (tmdb_id,),
    )
    return row.get("jellyfin_id") if row else None


async def _episode_exists(conn: aiosqlite.Connection, request: LibraryStateRequest) -> bool:
    season = request.season or 1
    series_id = await _series_id_for_tmdb(conn, request.tmdb_id)
    if series_id:
        row = await _fetch_one(
            conn,
            """
            SELECT id FROM jellyfin_library_items
            WHERE media_type = 'episode'
              AND series_jellyfin_id = ?
              AND season = ?
              AND episode = ?
            LIMIT 1
            """,
            (series_id, season, request.episode),
        )
        if row:
            return True

    for title_key in _request_title_keys(request):
        row = await _fetch_one(
            conn,
            """
            SELECT e.id FROM jellyfin_library_items e
            WHERE e.media_type = 'episode'
              AND e.normalized_series_title = ?
              AND e.season = ?
              AND e.episode = ?
              AND (
                  ? IS NULL
                  OR NOT EXISTS (
                      SELECT 1
                      FROM jellyfin_library_items s
                      WHERE s.media_type = 'series'
                        AND s.jellyfin_id = e.series_jellyfin_id
                        AND s.year IS NOT NULL
                        AND s.year <> ?
                  )
              )
            LIMIT 1
            """,
            (title_key, season, request.episode, request.year, request.year),
        )
        if row:
            return True
    return False


async def _series_episode_count(conn: aiosqlite.Connection, request: LibraryStateRequest) -> int:
    series_id = await _series_id_for_tmdb(conn, request.tmdb_id)
    if series_id:
        async with conn.execute(
            """
            SELECT COUNT(*) FROM jellyfin_library_items
            WHERE media_type = 'episode' AND series_jellyfin_id = ?
            """,
            (series_id,),
        ) as cursor:
            return int((await cursor.fetchone())[0] or 0)

    for title_key in _request_title_keys(request):
        async with conn.execute(
            """
            SELECT COUNT(*) FROM jellyfin_library_items e
            WHERE e.media_type = 'episode'
              AND e.normalized_series_title = ?
              AND (
                  ? IS NULL
                  OR NOT EXISTS (
                      SELECT 1
                      FROM jellyfin_library_items s
                      WHERE s.media_type = 'series'
                        AND s.jellyfin_id = e.series_jellyfin_id
                        AND s.year IS NOT NULL
                        AND s.year <> ?
                  )
              )
            """,
            (title_key, request.year, request.year),
        ) as cursor:
            count = int((await cursor.fetchone())[0] or 0)
        if count:
            return count
    return 0


async def _tv_state(conn: aiosqlite.Connection, request: LibraryStateRequest) -> dict | None:
    if request.episode:
        if await _episode_exists(conn, request):
            return {
                **state_payload("completed", f"E{int(request.episode)} 已入库", 1, 1),
                "source": "jellyfin_index",
                "target_season": int(request.season or 1),
                "target_episode": int(request.episode),
                "exact_episode_checked": True,
            }
        return None

    current = await _series_episode_count(conn, request)
    if current <= 0:
        return None
    total = request.progress_total
    completed = bool(total and current >= total)
    return {
        **state_payload(
            "completed" if completed else "partial",
            "已完整入库" if completed else (f"已入库 {current}/{total}" if total else f"已入库 {current} 集"),
            current,
            total,
        ),
        "source": "jellyfin_index",
    }


async def query_jellyfin_library_index_state(
    request: LibraryStateRequest,
    *,
    db_path: str = DB_PATH,
) -> dict | None:
    try:
        async with connect_db(db_path, row_factory=aiosqlite.Row) as conn:
            if request.media_type == "movie":
                return await _movie_state(conn, request)
            return await _tv_state(conn, request)
    except aiosqlite.Error:
        return None


async def query_jellyfin_library_index_states(
    requests: list[LibraryStateRequest],
    *,
    db_path: str = DB_PATH,
) -> dict[str, dict | None]:
    states: dict[str, dict | None] = {}
    for request in requests:
        states[request.cache_key] = await query_jellyfin_library_index_state(request, db_path=db_path)
    return states
