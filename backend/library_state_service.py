# -*- coding: utf-8 -*-
import asyncio
import time

from jellyfin_service import ensure_jellyfin_client
from jellyfin_library_index_service import has_jellyfin_library_index, query_jellyfin_library_index_states
from library_state_query_service import query_library_state
from library_state_request_service import LibraryStateRequest, build_library_state_request
from structured_logging import log_event


LIBRARY_STATE_CACHE_TTL_SECONDS = 90
LIBRARY_STATE_FAILURE_TTL_SECONDS = 180
LIBRARY_STATE_CIRCUIT_BREAKER_SECONDS = 60
LIBRARY_STATE_CIRCUIT_FAILURE_THRESHOLD = 5
LIBRARY_STATE_CONCURRENCY = 6
_LIBRARY_STATE_CACHE: dict[str, tuple[float, dict | None]] = {}
_LIBRARY_STATE_FAILURE_CACHE: dict[str, tuple[float, str | None]] = {}
_JELLYFIN_CIRCUIT_OPEN_UNTIL = 0.0


def clear_library_state_cache() -> None:
    _LIBRARY_STATE_CACHE.clear()
    _LIBRARY_STATE_FAILURE_CACHE.clear()
    global _JELLYFIN_CIRCUIT_OPEN_UNTIL
    _JELLYFIN_CIRCUIT_OPEN_UNTIL = 0.0


def _library_status_for_state(state: dict | None) -> str | None:
    if not state:
        return None
    status = state.get("status")
    if status == "completed":
        return "in_library"
    if status == "partial":
        return "partial_library"
    if status == "missing":
        return "missing"
    return None


def _get_cached_state(cache_key: str) -> dict | None | object:
    cached = _LIBRARY_STATE_CACHE.get(cache_key)
    if not cached:
        return _CACHE_MISS
    expires_at, state = cached
    if expires_at < time.monotonic():
        _LIBRARY_STATE_CACHE.pop(cache_key, None)
        return _CACHE_MISS
    return state


def _set_cached_state(cache_key: str, state: dict | None) -> None:
    _LIBRARY_STATE_CACHE[cache_key] = (time.monotonic() + LIBRARY_STATE_CACHE_TTL_SECONDS, state)


def _has_recent_failure(cache_key: str) -> bool:
    cached = _LIBRARY_STATE_FAILURE_CACHE.get(cache_key)
    if not cached:
        return False
    expires_at, _error = cached
    if expires_at < time.monotonic():
        _LIBRARY_STATE_FAILURE_CACHE.pop(cache_key, None)
        return False
    return True


def _set_cached_failure(cache_key: str, error: str | None) -> None:
    _LIBRARY_STATE_FAILURE_CACHE[cache_key] = (time.monotonic() + LIBRARY_STATE_FAILURE_TTL_SECONDS, error)


def _jellyfin_circuit_open() -> bool:
    return _JELLYFIN_CIRCUIT_OPEN_UNTIL > time.monotonic()


def _open_jellyfin_circuit() -> None:
    global _JELLYFIN_CIRCUIT_OPEN_UNTIL
    _JELLYFIN_CIRCUIT_OPEN_UNTIL = time.monotonic() + LIBRARY_STATE_CIRCUIT_BREAKER_SECONDS


_CACHE_MISS = object()


async def resolve_library_states_for_items(items: list[dict]) -> list[dict]:
    if not items:
        return []

    requests: list[LibraryStateRequest | None] = [
        build_library_state_request(item, index) for index, item in enumerate(items)
    ]
    valid_requests = [request for request in requests if request is not None]
    if not valid_requests:
        return [
            {"key": str(item.get("key")) if isinstance(item, dict) and item.get("key") is not None else str(index)}
            for index, item in enumerate(items)
        ]

    if await has_jellyfin_library_index():
        states_by_cache_key = await query_jellyfin_library_index_states(valid_requests)
        resolved: list[dict] = []
        for index, (item, request) in enumerate(zip(items, requests, strict=True)):
            key = request.key if request else (
                str(item.get("key")) if isinstance(item, dict) and item.get("key") is not None else str(index)
            )
            payload = {"key": key}
            if request:
                state = states_by_cache_key.get(request.cache_key)
                if state and state.get("status") not in {"missing", "query_failed"}:
                    payload["library_state"] = state
                    library_status = _library_status_for_state(state)
                    if library_status:
                        payload["library_status"] = library_status
            resolved.append(payload)
        return resolved

    if _jellyfin_circuit_open():
        return [
            {"key": request.key if request else (str(item.get("key")) if isinstance(item, dict) and item.get("key") is not None else str(index))}
            for index, (item, request) in enumerate(zip(items, requests, strict=True))
        ]

    jellyfin = await ensure_jellyfin_client()
    if not jellyfin:
        return [
            {"key": request.key if request else (str(item.get("key")) if isinstance(item, dict) and item.get("key") is not None else str(index))}
            for index, (item, request) in enumerate(zip(items, requests, strict=True))
        ]

    states_by_cache_key: dict[str, dict | None] = {}
    missing_by_cache_key: dict[str, LibraryStateRequest] = {}
    for request in valid_requests:
        cached = _get_cached_state(request.cache_key)
        if cached is _CACHE_MISS:
            if _has_recent_failure(request.cache_key):
                states_by_cache_key[request.cache_key] = None
            else:
                missing_by_cache_key.setdefault(request.cache_key, request)
        else:
            states_by_cache_key[request.cache_key] = cached

    semaphore = asyncio.Semaphore(LIBRARY_STATE_CONCURRENCY)
    failed_count = {"value": 0}

    async def resolve_one(cache_key: str, request: LibraryStateRequest) -> None:
        async with semaphore:
            state = await query_library_state(request, jellyfin)
            if state and state.get("status") == "query_failed":
                failed_count["value"] += 1
                _set_cached_failure(cache_key, state.get("error"))
                _set_cached_state(cache_key, None)
                states_by_cache_key[cache_key] = None
                return
            _set_cached_state(cache_key, state)
            states_by_cache_key[cache_key] = state

    if missing_by_cache_key:
        await asyncio.gather(*(resolve_one(cache_key, request) for cache_key, request in missing_by_cache_key.items()))
        if failed_count["value"]:
            log_event("library_state.query_failed", "warning", failed_count=failed_count["value"])
        if failed_count["value"] >= LIBRARY_STATE_CIRCUIT_FAILURE_THRESHOLD:
            _open_jellyfin_circuit()
            log_event(
                "library_state.circuit_opened",
                "warning",
                failed_count=failed_count["value"],
                seconds=LIBRARY_STATE_CIRCUIT_BREAKER_SECONDS,
            )

    resolved: list[dict] = []
    for index, (item, request) in enumerate(zip(items, requests, strict=True)):
        key = request.key if request else (
            str(item.get("key")) if isinstance(item, dict) and item.get("key") is not None else str(index)
        )
        payload = {"key": key}
        if request:
            state = states_by_cache_key.get(request.cache_key)
            if state and state.get("status") not in {"missing", "query_failed"}:
                payload["library_state"] = state
                library_status = _library_status_for_state(state)
                if library_status:
                    payload["library_status"] = library_status
        resolved.append(payload)
    return resolved


def _apply_state_to_item(item: dict, state_payload: dict) -> None:
    state = state_payload.get("library_state")
    if not state:
        return
    item["library_state"] = state
    if state_payload.get("library_status"):
        item["library_status"] = state_payload["library_status"]


async def annotate_tmdb_search_items_with_jellyfin_state(items: list[dict]) -> list[dict]:
    if not items:
        return items
    states = await resolve_library_states_for_items(items)
    for item, state_payload in zip(items, states, strict=True):
        if isinstance(item, dict):
            if state_payload.get("library_state", {}).get("status") == "missing":
                continue
            _apply_state_to_item(item, state_payload)
    return items


async def annotate_search_results_with_jellyfin_state(items: list[dict]) -> list[dict]:
    if not items:
        return items
    states = await resolve_library_states_for_items(items)
    for item, state_payload in zip(items, states, strict=True):
        if isinstance(item, dict):
            _apply_state_to_item(item, state_payload)
    return items
