# -*- coding: utf-8 -*-
import aiosqlite

from structured_logging import log_event


async def ensure_columns(conn: aiosqlite.Connection, table_name: str, columns: dict[str, str]) -> None:
    async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
        existing_columns = {row[1] for row in await cursor.fetchall()}
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            await conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


async def ensure_messages_fts(conn: aiosqlite.Connection) -> None:
    try:
        async with conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'messages_fts'"
        ) as cursor:
            existed = await cursor.fetchone() is not None

        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                title,
                description,
                raw_text,
                content='messages',
                content_rowid='id',
                tokenize='unicode61'
            )
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, title, description, raw_text)
                VALUES (new.id, new.title, new.description, new.raw_text);
            END;
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, title, description, raw_text)
                VALUES('delete', old.id, old.title, old.description, old.raw_text);
            END;
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE OF title, description, raw_text ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, title, description, raw_text)
                VALUES('delete', old.id, old.title, old.description, old.raw_text);
                INSERT INTO messages_fts(rowid, title, description, raw_text)
                VALUES (new.id, new.title, new.description, new.raw_text);
            END;
        """)
        async with conn.execute("SELECT value FROM config WHERE key = 'messages_fts_initialized'") as cursor:
            initialized = await cursor.fetchone() is not None
        if not existed or not initialized:
            await conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
            await conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES ('messages_fts_initialized', CURRENT_TIMESTAMP)"
            )
    except aiosqlite.Error as exc:
        log_event("db_migration.messages_fts_failed", "warning", error_type=type(exc).__name__)


async def ensure_links_scoped_uniqueness(conn: aiosqlite.Connection) -> None:
    async with conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'links'") as cursor:
        row = await cursor.fetchone()
    create_sql = row[0] if row else ""
    if "url TEXT NOT NULL UNIQUE" not in create_sql:
        return

    await conn.execute("DROP TABLE IF EXISTS links_migration_old")
    await conn.execute("ALTER TABLE links RENAME TO links_migration_old")
    await conn.execute("""
        CREATE TABLE links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            url TEXT NOT NULL,
            label TEXT,
            FOREIGN KEY (message_id) REFERENCES messages (id)
        )
    """)
    await conn.execute("""
        INSERT INTO links (id, message_id, url, label)
        SELECT MIN(id), message_id, url, MAX(label)
        FROM links_migration_old
        WHERE message_id IS NOT NULL AND url IS NOT NULL
        GROUP BY message_id, url
    """)
    await conn.execute("DROP TABLE links_migration_old")
