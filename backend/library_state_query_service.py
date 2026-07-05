# -*- coding: utf-8 -*-
import asyncio

from library_state_request_service import LibraryStateRequest


def state_payload(status: str, label: str, current: int = 0, total: int = 0) -> dict:
    return {
        "status": status,
        "label": label,
        "progress_current": current,
        "progress_total": total,
    }


async def query_library_state(request: LibraryStateRequest, jellyfin) -> dict | None:
    try:
        if request.media_type == "movie":
            if request.tmdb_id and hasattr(jellyfin, "search_movie_by_tmdb_id"):
                movie = await asyncio.wait_for(
                    jellyfin.search_movie_by_tmdb_id(request.tmdb_id),
                    timeout=6,
                )
                if movie:
                    return state_payload("completed", "已入库", 1, 1)
            exists = await asyncio.wait_for(
                jellyfin.check_movie_exists(request.check_title, request.year),
                timeout=6,
            )
            if exists:
                return state_payload("completed", "已入库", 1, 1)
            return state_payload("missing", "未入库", 0, 1)

        if request.episode:
            season = request.season or 1
            exists = False
            if request.tmdb_id and hasattr(jellyfin, "search_series_by_tmdb_id"):
                series = await asyncio.wait_for(
                    jellyfin.search_series_by_tmdb_id(request.tmdb_id),
                    timeout=6,
                )
                series_id = series.get("Id") if series else None
                if series_id:
                    episodes = await asyncio.wait_for(
                        jellyfin.get_season_episodes(series_id, season),
                        timeout=6,
                    )
                    exists = request.episode in episodes
            if not exists:
                exists = await asyncio.wait_for(
                    jellyfin.check_episode_exists(request.check_title, season, request.episode, request.year),
                    timeout=6,
                )
            if exists:
                return state_payload("completed", f"E{int(request.episode):02d} 已入库", 1, 1)
            return state_payload("missing", f"E{int(request.episode):02d} 未入库", 0, 1)

        existing_by_season = {}
        if request.tmdb_id and hasattr(jellyfin, "search_series_by_tmdb_id"):
            series = await asyncio.wait_for(
                jellyfin.search_series_by_tmdb_id(request.tmdb_id),
                timeout=6,
            )
            series_id = series.get("Id") if series else None
            if series_id and hasattr(jellyfin, "get_series_episodes_by_season_id"):
                existing_by_season = await asyncio.wait_for(
                    jellyfin.get_series_episodes_by_season_id(series_id),
                    timeout=8,
                )
        if not existing_by_season:
            existing_by_season = await asyncio.wait_for(
                jellyfin.get_series_episodes_by_season(request.check_title, request.year),
                timeout=8,
            )
        current = sum(len(set(episodes)) for episodes in existing_by_season.values())
        total = request.progress_total
        if current > 0:
            completed = bool(total and current >= total)
            return state_payload(
                "completed" if completed else "partial",
                "已完整入库" if completed else (f"已入库 {current}/{total}" if total else f"已入库 {current} 集"),
                current,
                total,
            )
        return state_payload("missing", "未入库", 0, total or 1)
    except Exception as exc:
        return {"status": "query_failed", "error": str(exc), "label": "查询失败"}
