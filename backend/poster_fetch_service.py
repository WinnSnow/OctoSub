# -*- coding: utf-8 -*-
from dataclasses import dataclass

from fastapi import HTTPException

from poster_identity_service import MediaIdentity
from poster_service import fetch_movie_poster, poster_url_from_path
from structured_logging import log_event
from tmdb_service import fetch_tmdb_json


@dataclass
class PosterMatchResult:
    poster_url: str | None
    source: str
    miss: bool = False


async def fetch_tmdb_id_poster(identity: MediaIdentity, proxy_config: dict | None = None) -> str | None:
    if not identity.tmdb_id:
        return None

    media_types = [identity.media_type] if identity.media_type in {"movie", "tv"} else ["movie", "tv"]
    for media_type in media_types:
        try:
            data = await fetch_tmdb_json(f"{media_type}/{identity.tmdb_id}", proxy_config=proxy_config)
        except HTTPException as exc:
            if exc.status_code == 400:
                log_event("poster.tmdb_id.skipped", "warning", reason="tmdb_api_key_missing")
                return None
            continue
        except Exception as exc:
            log_event(
                "poster.tmdb_id.request_failed",
                "warning",
                media_type=media_type,
                tmdb_id=identity.tmdb_id,
                error=str(exc),
            )
            continue

        poster_url = poster_url_from_path(data.get("poster_path"))
        if poster_url:
            return poster_url
    return None


async def fetch_poster_for_identity(identity: MediaIdentity, proxy_config: dict | None = None) -> PosterMatchResult:
    if identity.tmdb_id:
        poster_url = await fetch_tmdb_id_poster(identity, proxy_config)
        return PosterMatchResult(poster_url=poster_url, source="tmdb_id_api", miss=not bool(poster_url))

    if not identity.clean_title:
        return PosterMatchResult(poster_url=None, source="invalid_title", miss=True)

    search_title = f"{identity.clean_title} ({identity.year})" if identity.year else identity.clean_title
    poster_url = await fetch_movie_poster(search_title, proxy_config, media_type=identity.media_type)
    return PosterMatchResult(poster_url=poster_url, source="tmdb_search_api", miss=not bool(poster_url))
