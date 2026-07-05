# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

import aiosqlite

from config import DB_PATH
from db_schema_service import ensure_database_schema
from db_seed_service import prepare_startup_data_for_connection


@asynccontextmanager
async def connect_db(db_path: str | None = None, *, timeout: float = 30.0, row_factory=None):  # noqa: ASYNC109
    conn = await aiosqlite.connect(db_path or DB_PATH, timeout=timeout)
    try:
        await conn.execute("PRAGMA foreign_keys = ON;")
        await conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")
        if row_factory is not None:
            conn.row_factory = row_factory
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    async with connect_db() as conn:
        await conn.execute("PRAGMA journal_mode=WAL;")
        await ensure_database_schema(conn)
        await conn.commit()


async def prepare_startup_data() -> None:
    async with connect_db() as conn:
        await prepare_startup_data_for_connection(conn)
        await conn.commit()
