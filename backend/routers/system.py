# -*- coding: utf-8 -*-
from fastapi import APIRouter
from fastapi import Query

from system_service import cleanup_system_cache_payload, get_system_status_payload


router = APIRouter()


@router.get("/api/system/status")
async def get_system_status():
    return await get_system_status_payload()


@router.post("/api/system/cache/cleanup")
async def cleanup_system_cache(table: str | None = Query(default=None)):
    return await cleanup_system_cache_payload(table)
