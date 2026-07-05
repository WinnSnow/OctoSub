# -*- coding: utf-8 -*-
import aiosqlite

from db_migration_service import ensure_columns


RESOURCE_INDEX_COMPAT_COLUMNS = {
    "channel_name": "TEXT",
    "source_message_id": "INTEGER",
    "title": "TEXT",
    "description": "TEXT",
    "raw_text": "TEXT",
    "link_type": "TEXT",
    "tmdb_id": "INTEGER",
    "tmdb_type": "TEXT",
    "year": "INTEGER",
    "season": "INTEGER",
    "episode": "INTEGER",
    "quality_tags_json": "TEXT",
    "publish_date": "TIMESTAMP",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


async def ensure_resource_index_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS resource_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            channel_name TEXT,
            source_message_id INTEGER,
            title TEXT,
            description TEXT,
            raw_text TEXT,
            url TEXT NOT NULL,
            link_type TEXT,
            tmdb_id INTEGER,
            tmdb_type TEXT,
            year INTEGER,
            season INTEGER,
            episode INTEGER,
            quality_tags_json TEXT,
            publish_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(message_id, url),
            FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
        )
    """)
    await ensure_columns(conn, "resource_index", RESOURCE_INDEX_COMPAT_COLUMNS)
    await conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS resource_index_fts USING fts5(
            title,
            description,
            raw_text,
            url,
            content='resource_index',
            content_rowid='id',
            tokenize='unicode61'
        )
    """)
    await conn.execute("""
        CREATE TRIGGER IF NOT EXISTS resource_index_fts_ai AFTER INSERT ON resource_index BEGIN
            INSERT INTO resource_index_fts(rowid, title, description, raw_text, url)
            VALUES (new.id, new.title, new.description, new.raw_text, new.url);
        END;
    """)
    await conn.execute("""
        CREATE TRIGGER IF NOT EXISTS resource_index_fts_ad AFTER DELETE ON resource_index BEGIN
            INSERT INTO resource_index_fts(resource_index_fts, rowid, title, description, raw_text, url)
            VALUES('delete', old.id, old.title, old.description, old.raw_text, old.url);
        END;
    """)
    await conn.execute("""
        CREATE TRIGGER IF NOT EXISTS resource_index_fts_au AFTER UPDATE OF title, description, raw_text, url ON resource_index BEGIN
            INSERT INTO resource_index_fts(resource_index_fts, rowid, title, description, raw_text, url)
            VALUES('delete', old.id, old.title, old.description, old.raw_text, old.url);
            INSERT INTO resource_index_fts(rowid, title, description, raw_text, url)
            VALUES (new.id, new.title, new.description, new.raw_text, new.url);
        END;
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_resource_index_publish ON resource_index(publish_date, id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_resource_index_channel_publish ON resource_index(channel_name, publish_date)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_resource_index_message ON resource_index(message_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_resource_index_link_type ON resource_index(link_type)")


async def resource_index_available(conn: aiosqlite.Connection) -> bool:
    async with conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resource_index'"
    ) as cursor:
        return await cursor.fetchone() is not None


async def resource_index_fts_available(conn: aiosqlite.Connection) -> bool:
    async with conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resource_index_fts'"
    ) as cursor:
        return await cursor.fetchone() is not None
