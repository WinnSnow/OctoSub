# -*- coding: utf-8 -*-
"""
Database schema creation, compatibility migrations, and hot-path indexes.
"""
import aiosqlite

from config import SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE
from db_migration_service import ensure_columns, ensure_links_scoped_uniqueness, ensure_messages_fts


async def create_base_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, channel_name TEXT, message_id INTEGER,
            title TEXT, description TEXT, language TEXT, type TEXT, actors TEXT,
            image_url TEXT, raw_text TEXT, publish_date TIMESTAMP, resource_url TEXT,
            tmdb_id INTEGER, tmdb_type TEXT, year INTEGER,
            douban_id TEXT, douban_url TEXT, douban_rating REAL,
            UNIQUE(channel_name, message_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER,
            url TEXT NOT NULL, label TEXT,
            FOREIGN KEY (message_id) REFERENCES messages (id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            quality_filter TEXT,
            media_type TEXT NOT NULL DEFAULT 'tv',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tmdb_id INTEGER,
            tmdb_type TEXT,
            year INTEGER,
            poster_url TEXT,
            douban_id TEXT,
            douban_url TEXT,
            douban_rating REAL,
            metadata_source TEXT,
            target_seasons_json TEXT,
            CHECK (media_type IN ('tv', 'movie'))
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS download_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INTEGER,
            title TEXT,
            fingerprint TEXT NOT NULL,
            link TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'success',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions (id) ON DELETE SET NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS search_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS poster_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS douban_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INTEGER,
            result_id TEXT NOT NULL,
            title TEXT,
            link TEXT NOT NULL,
            password TEXT,
            confidence REAL DEFAULT 0,
            match_reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            payload_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions (id) ON DELETE SET NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            total INTEGER DEFAULT 0,
            current INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            message TEXT,
            result_json TEXT,
            error TEXT,
            metadata_json TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            finished_at REAL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS jellyfin_library_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jellyfin_id TEXT NOT NULL UNIQUE,
            series_jellyfin_id TEXT,
            media_type TEXT NOT NULL,
            title TEXT,
            normalized_title TEXT,
            series_title TEXT,
            normalized_series_title TEXT,
            year INTEGER,
            tmdb_id INTEGER,
            season INTEGER,
            episode INTEGER,
            payload_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


async def ensure_compat_schema(conn: aiosqlite.Connection) -> None:
    await ensure_messages_fts(conn)

    await ensure_columns(conn, "search_cache", {
        "payload_json": "TEXT",
        "expires_at": "REAL DEFAULT 0",
    })
    await ensure_columns(conn, "poster_cache", {
        "payload_json": "TEXT",
        "expires_at": "REAL DEFAULT 0",
    })
    await ensure_columns(conn, "douban_cache", {
        "payload_json": "TEXT",
        "expires_at": "REAL DEFAULT 0",
    })
    await ensure_columns(conn, "messages", {
        "tmdb_id": "INTEGER",
        "tmdb_type": "TEXT",
        "year": "INTEGER",
        "douban_id": "TEXT",
        "douban_url": "TEXT",
        "douban_rating": "REAL",
    })
    await ensure_columns(conn, "pending_transfers", {
        "password": "TEXT",
        "confidence": "REAL DEFAULT 0",
        "match_reason": "TEXT",
        "status": "TEXT DEFAULT 'pending'",
        "payload_json": "TEXT",
        "updated_at": "TIMESTAMP",
    })
    await ensure_columns(conn, "download_history", {
        "title": "TEXT",
        "callback_message": "TEXT",
        "updated_at": "TIMESTAMP",
    })
    await ensure_columns(conn, "subscriptions", {
        "tmdb_id": "INTEGER",
        "tmdb_type": "TEXT",
        "year": "INTEGER",
        "poster_url": "TEXT",
        "enabled": "INTEGER DEFAULT 1",
        "auto_transfer": "INTEGER DEFAULT 1",
        "min_confidence": f"REAL DEFAULT {SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE}",
        "last_checked_at": "TIMESTAMP",
        "status": "TEXT DEFAULT 'active'",
        "completed_at": "TIMESTAMP",
        "completion_reason": "TEXT",
        "progress_current": "INTEGER DEFAULT 0",
        "progress_total": "INTEGER DEFAULT 0",
        "episode_state_json": "TEXT",
        "target_seasons_json": "TEXT",
        "douban_id": "TEXT",
        "douban_url": "TEXT",
        "douban_rating": "REAL",
        "metadata_source": "TEXT",
    })
    await ensure_links_scoped_uniqueness(conn)


async def ensure_hot_path_indexes(conn: aiosqlite.Connection) -> None:
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel_publish ON messages(channel_name, publish_date)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel_publish_id ON messages(channel_name, publish_date, id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_publish ON messages(publish_date)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_publish_id ON messages(publish_date, id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_title ON messages(title)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_resource_url ON messages(resource_url)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_links_message_id ON links(message_id)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_links_message_url ON links(message_id, url)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_keyword ON subscriptions(keyword)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status_id ON subscriptions(status, id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_download_history_subscription ON download_history(subscription_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_download_history_status_id ON download_history(status, id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_download_history_subscription_status_id ON download_history(subscription_id, status, id)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_download_history_fingerprint ON download_history(fingerprint)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_download_history_link ON download_history(link)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_poster_cache_expires ON poster_cache(expires_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_douban_cache_expires ON douban_cache(expires_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_douban_id ON subscriptions(douban_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_douban_id ON messages(douban_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_transfers_status ON pending_transfers(status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_transfers_status_id ON pending_transfers(status, id)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_transfers_unique ON pending_transfers(subscription_id, result_id, link)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at, created_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_updated ON tasks(status, updated_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_type_updated ON tasks(type, updated_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jellyfin_library_tmdb ON jellyfin_library_items(media_type, tmdb_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jellyfin_library_title ON jellyfin_library_items(media_type, normalized_title, year)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jellyfin_library_episode ON jellyfin_library_items(normalized_series_title, season, episode)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jellyfin_library_series_id ON jellyfin_library_items(series_jellyfin_id, season, episode)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jellyfin_library_updated ON jellyfin_library_items(updated_at)")


async def ensure_database_schema(conn: aiosqlite.Connection) -> None:
    await create_base_schema(conn)
    await ensure_compat_schema(conn)
    await ensure_hot_path_indexes(conn)
