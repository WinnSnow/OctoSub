# -*- coding: utf-8 -*-
from db import connect_db
from poster_identity_service import build_media_identity


def build_local_poster_reuse_keys(
    title: str | None,
    raw_text: str | None,
    tmdb_id: int | None,
    tmdb_type: str | None,
    year: int | None,
) -> list[str]:
    identity = build_media_identity(title, raw_text, tmdb_id, tmdb_type, year)
    keys: list[str] = []
    if identity.tmdb_id:
        keys.append(f"tmdb:{identity.media_type or 'unknown'}:{identity.tmdb_id}")
    if identity.clean_title and identity.year:
        clean_title = identity.clean_title.lower()
        keys.append(f"title:{identity.media_type or 'unknown'}:{clean_title}:{identity.year}")
        keys.append(f"title:any:{clean_title}:{identity.year}")
    return list(dict.fromkeys(keys))


async def load_existing_tmdb_posters_by_key(
    db_path: str,
    excluded_message_ids: set[int] | None = None,
) -> dict[str, str]:
    excluded_message_ids = excluded_message_ids or set()
    existing: dict[str, str] = {}
    async with connect_db(db_path) as conn:
        async with conn.execute(
            """
            SELECT id, title, raw_text, image_url, tmdb_id, tmdb_type, year
            FROM messages
            WHERE image_url LIKE 'https://image.tmdb.org/%'
              AND title IS NOT NULL
              AND title != ''
            """
        ) as cursor:
            rows = await cursor.fetchall()

    for msg_id, title, raw_text, image_url, tmdb_id, tmdb_type, year in rows:
        if msg_id in excluded_message_ids or not image_url:
            continue
        for key in build_local_poster_reuse_keys(title, raw_text, tmdb_id, tmdb_type, year):
            existing.setdefault(key, image_url)
    return existing


async def read_target_messages(
    db_path: str,
    message_ids: list[int] | None = None,
) -> list[tuple[int, str, str | None, str | None, int | None, str | None, int | None]]:
    params: list[object] = []
    id_clause = ""
    if message_ids is not None:
        if not message_ids:
            return []
        placeholders = ",".join("?" for _ in message_ids)
        id_clause = f"AND id IN ({placeholders})"
        params.extend(message_ids)

    async with connect_db(db_path) as conn:
        async with conn.execute(
            f"""
            SELECT id, title, raw_text, image_url, tmdb_id, tmdb_type, year
            FROM messages
            WHERE title IS NOT NULL
              AND title != ''
              AND (
                image_url IS NULL
                OR image_url = ''
                OR image_url NOT LIKE 'https://image.tmdb.org/%'
              )
              {id_clause}
            """,
            tuple(params),
        ) as cursor:
            return await cursor.fetchall()
