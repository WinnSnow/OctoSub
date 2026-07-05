# -*- coding: utf-8 -*-
import time

from config import DB_PATH
from db import connect_db


async def check_database_connectivity(db_path: str = DB_PATH, *, timeout_seconds: float = 1.5) -> dict:
    started_at = time.perf_counter()
    async with connect_db(db_path, timeout=timeout_seconds) as conn:
        async with conn.execute("SELECT 1") as cursor:
            await cursor.fetchone()
    return {"latency_ms": round((time.perf_counter() - started_at) * 1000, 2)}
