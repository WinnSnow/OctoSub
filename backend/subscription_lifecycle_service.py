# -*- coding: utf-8 -*-
import json

from jellyfin_service import ensure_jellyfin_client
from structured_logging import log_event
from subscription_repository import list_subscription_lifecycle_rows, persist_subscription_lifecycle_state
from subscription_state_service import attach_subscription_state, get_subscription_state_maps
from tmdb_service import fetch_tmdb_tv_episode_targets


SUBSCRIPTION_TARGETED_SEARCH_TERM_LIMIT = 40


def _episode_map_payload(values_by_season: dict[int, set[int]]) -> dict[str, list[int]]:
    return {
        str(int(season)): sorted(int(episode) for episode in episodes)
        for season, episodes in sorted(values_by_season.items())
    }


def normalize_target_seasons(value) -> set[int] | None:
    if value in (None, "", []):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    if not isinstance(value, (list, tuple, set)):
        return None
    try:
        seasons = {int(item) for item in value if int(item) > 0}
    except Exception:
        return None
    return seasons or None


def filter_episode_targets_by_seasons(
    targets: dict[int, set[int]],
    target_seasons=None,
) -> dict[int, set[int]]:
    seasons = normalize_target_seasons(target_seasons)
    if not seasons:
        return targets
    return {
        int(season): set(episodes)
        for season, episodes in targets.items()
        if int(season) in seasons
    }


def build_episode_state(
    targets: dict[int, set[int]],
    existing_by_season: dict[int, list[int] | set[int]],
    target_seasons=None,
) -> dict:
    targets = filter_episode_targets_by_seasons(targets, target_seasons)
    expected_by_season: dict[int, set[int]] = {}
    existing_target_by_season: dict[int, set[int]] = {}
    missing_by_season: dict[int, set[int]] = {}
    historical_missing_by_season: dict[int, set[int]] = {}
    future_available_missing_by_season: dict[int, set[int]] = {}
    next_missing = None
    max_existing = None

    for season_number, expected_episodes in sorted(targets.items()):
        expected = {int(episode) for episode in expected_episodes}
        existing = {int(episode) for episode in existing_by_season.get(season_number, [])}
        existing_target = expected.intersection(existing)
        missing = expected - existing
        expected_by_season[int(season_number)] = expected
        existing_target_by_season[int(season_number)] = existing_target
        missing_by_season[int(season_number)] = missing
        if next_missing is None and missing:
            next_missing = {"season": int(season_number), "episode": min(missing)}

        if existing_target:
            latest_for_season = max(existing_target)
            season_key = int(season_number)
            if max_existing is None or (season_key, latest_for_season) > (
                max_existing["season"],
                max_existing["episode"],
            ):
                max_existing = {"season": season_key, "episode": latest_for_season}

    auto_search_target = None
    if expected_by_season:
        if max_existing is None:
            first_season = min(expected_by_season)
            first_episode = min(expected_by_season[first_season])
            auto_search_target = {"season": first_season, "episode": first_episode}
        else:
            season_number = int(max_existing["season"])
            next_episode = int(max_existing["episode"]) + 1
            if next_episode in expected_by_season.get(season_number, set()):
                auto_search_target = {"season": season_number, "episode": next_episode}
            else:
                next_seasons = [
                    season
                    for season in sorted(expected_by_season)
                    if season > season_number and expected_by_season[season]
                ]
                if next_seasons:
                    next_season = next_seasons[0]
                    auto_search_target = {
                        "season": next_season,
                        "episode": min(expected_by_season[next_season]),
                    }

    for season_number, missing in missing_by_season.items():
        historical_missing_by_season[season_number] = set()
        future_available_missing_by_season[season_number] = set()

        if max_existing is None:
            future_available_missing_by_season[season_number] = set(missing)
        else:
            max_season = int(max_existing["season"])
            max_episode = int(max_existing["episode"])
            if season_number < max_season:
                historical_missing_by_season[season_number] = set(missing)
            elif season_number == max_season:
                historical_missing_by_season[season_number] = {
                    episode for episode in missing if episode < max_episode
                }
                future_available_missing_by_season[season_number] = {
                    episode for episode in missing if episode > max_episode
                }
            else:
                future_available_missing_by_season[season_number] = set(missing)

    if auto_search_target:
        target_season = int(auto_search_target["season"])
        target_episode = int(auto_search_target["episode"])
        future_available_missing_by_season.setdefault(target_season, set()).discard(target_episode)

    return {
        "expected_episodes": _episode_map_payload(expected_by_season),
        "existing_episodes": _episode_map_payload(existing_target_by_season),
        "missing_episodes": _episode_map_payload(missing_by_season),
        "historical_missing": _episode_map_payload(historical_missing_by_season),
        "future_available_missing": _episode_map_payload(future_available_missing_by_season),
        "next_missing": next_missing,
        "max_existing": max_existing,
        "auto_search_target": auto_search_target,
    }


def episode_state_counts(episode_state: dict) -> tuple[int, int]:
    expected = episode_state.get("expected_episodes") or {}
    existing = episode_state.get("existing_episodes") or {}
    total = sum(len(episodes or []) for episodes in expected.values())
    current = sum(len(episodes or []) for episodes in existing.values())
    return current, total


async def get_subscription_episode_progress(
    jellyfin,
    title: str,
    year: int | None,
    tmdb_id: int | None,
    target_seasons=None,
    proxy_config: dict | None = None,
) -> tuple[int, int]:
    if not jellyfin:
        return 0, 0

    targets = await fetch_tmdb_tv_episode_targets(tmdb_id, proxy_config)
    if not targets:
        return 0, 0

    try:
        existing_by_season = await jellyfin.get_series_episodes_by_season(title, year)
    except Exception as exc:
        log_event("subscription.lifecycle.episode_progress_failed", "warning", error_type=type(exc).__name__)
        filtered_targets = filter_episode_targets_by_seasons(targets, target_seasons)
        return 0, sum(len(episodes) for episodes in filtered_targets.values())

    return episode_state_counts(build_episode_state(targets, existing_by_season, target_seasons))


async def get_missing_subscription_episodes(
    subscription: dict,
    jellyfin,
    proxy_config: dict | None = None,
) -> list[dict]:
    if not jellyfin:
        return []
    media_type = subscription.get("tmdb_type") or subscription.get("media_type")
    if media_type != "tv":
        return []

    keyword = subscription.get("keyword")
    tmdb_id = subscription.get("tmdb_id")
    year = subscription.get("year")
    if not keyword or not tmdb_id:
        return []

    targets = await fetch_tmdb_tv_episode_targets(tmdb_id, proxy_config)
    if not targets:
        return []

    existing_by_season = await jellyfin.get_series_episodes_by_season(keyword, year)
    episode_state = build_episode_state(targets, existing_by_season, subscription.get("target_seasons"))
    auto_search_target = episode_state.get("auto_search_target") or {}
    season_number = auto_search_target.get("season")
    episode_number = auto_search_target.get("episode")
    if not season_number or not episode_number:
        return []
    return [{
        "season": int(season_number),
        "episode": int(episode_number),
        "search_terms": [
            f"{keyword} S{int(season_number):02d}E{int(episode_number):02d}",
            f"{keyword} S{int(season_number)}E{int(episode_number)}",
            f"{keyword} 第{int(season_number)}季 第{int(episode_number)}集",
            f"{keyword} 第{int(episode_number)}集",
            f"{keyword} EP{int(episode_number):02d}",
        ],
    }]


def build_subscription_targeted_search_terms(
    subscription: dict,
    missing_episodes: list[dict],
    fallback_terms: list[str] | None = None,
) -> list[str]:
    terms = []
    if missing_episodes:
        for episode in missing_episodes[:20]:
            terms.extend(episode.get("search_terms") or [])
        return list(dict.fromkeys(term for term in terms if term))[:SUBSCRIPTION_TARGETED_SEARCH_TERM_LIMIT]
    terms.extend(fallback_terms or [])
    return list(dict.fromkeys(term for term in terms if term))[:SUBSCRIPTION_TARGETED_SEARCH_TERM_LIMIT]


async def persist_subscription_lifecycle(
    subscription_id: int,
    status: str,
    reason: str | None,
    progress_current: int,
    progress_total: int,
    episode_state: dict | None = None,
) -> None:
    await persist_subscription_lifecycle_state(
        subscription_id,
        status,
        reason,
        progress_current,
        progress_total,
        episode_state,
    )


async def evaluate_subscription_completion(
    subscription: dict,
    jellyfin,
    proxy_config: dict | None = None,
) -> dict | None:
    if not jellyfin:
        return None

    sub_id = subscription.get("id")
    keyword = subscription.get("keyword")
    media_type = subscription.get("tmdb_type") or subscription.get("media_type")
    year = subscription.get("year")
    tmdb_id = subscription.get("tmdb_id")
    if not sub_id or not keyword or media_type not in {"movie", "tv"}:
        return None

    try:
        if media_type == "movie":
            exists = await jellyfin.check_movie_exists(keyword, year)
            state = {
                "status": "completed" if exists else "active",
                "reason": "jellyfin_movie_exists" if exists else None,
                "progress_current": 1 if exists else 0,
                "progress_total": 1,
                "episode_state": {},
            }
            await persist_subscription_lifecycle(
                sub_id,
                state["status"],
                state["reason"],
                state["progress_current"],
                state["progress_total"],
                state["episode_state"],
            )
            return state

        targets = await fetch_tmdb_tv_episode_targets(tmdb_id, proxy_config)
        existing_by_season = await jellyfin.get_series_episodes_by_season(keyword, year)
        episode_state = build_episode_state(targets, existing_by_season, subscription.get("target_seasons"))
        current, total = episode_state_counts(episode_state)
        completed = total > 0 and current >= total
        state = {
            "status": "completed" if completed else "active",
            "reason": "jellyfin_tv_complete" if completed else None,
            "progress_current": current,
            "progress_total": total,
            "episode_state": episode_state,
        }
        await persist_subscription_lifecycle(
            sub_id,
            state["status"],
            state["reason"],
            state["progress_current"],
            state["progress_total"],
            state["episode_state"],
        )
        return state
    except Exception as exc:
        log_event(
            "subscription.lifecycle.completion_sync_failed",
            "warning",
            subscription_id=sub_id,
            error_type=type(exc).__name__,
        )
        return None


async def refresh_subscription_lifecycle_for_ids(
    subscription_ids: set[int] | list[int] | tuple[int, ...],
    proxy_config: dict | None = None,
) -> None:
    ids = [int(item) for item in subscription_ids if item]
    if not ids:
        return
    jellyfin = await ensure_jellyfin_client()
    if not jellyfin:
        return

    rows = await list_subscription_lifecycle_rows(ids)

    for row in rows:
        if row.get("status") == "completed":
            continue
        await evaluate_subscription_completion(row, jellyfin, proxy_config)


async def refresh_subscription_lifecycle_for_items(
    items: list[dict],
    proxy_config: dict | None = None,
) -> None:
    if not items:
        return
    by_tmdb, by_identity = await get_subscription_state_maps()
    subscription_ids: set[int] = set()
    for item in items:
        state = attach_subscription_state(item.copy(), by_tmdb, by_identity).get("subscription_state")
        if state and state.get("subscription_id") and state.get("status") != "completed":
            subscription_ids.add(int(state["subscription_id"]))
    await refresh_subscription_lifecycle_for_ids(subscription_ids, proxy_config)
