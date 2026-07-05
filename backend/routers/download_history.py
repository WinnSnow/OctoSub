# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, Query

import download_history_service
from config import DB_PATH
from schemas import DownloadHistoryPayload


router = APIRouter()


async def count_submitted_download_history(db_path: str = DB_PATH) -> int:
    return await download_history_service.count_submitted_download_history(db_path)


@router.get("/api/download-history")
async def get_download_history(
    subscription_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
):
    return await download_history_service.get_download_history_payload(
        subscription_id=subscription_id,
        status=status,
        page=page,
        limit=limit,
        db_path=DB_PATH,
    )


@router.post("/api/download-history/sync-cms")
async def sync_download_history_from_cms(background_tasks: BackgroundTasks):
    return await download_history_service.sync_download_history_from_cms_task(background_tasks, db_path=DB_PATH)


@router.post("/api/download-history/{history_id}/retry")
async def retry_download_history_transfer(history_id: int, background_tasks: BackgroundTasks):
    return await download_history_service.retry_download_history_transfer_task(
        history_id,
        background_tasks,
        db_path=DB_PATH,
    )


@router.post("/api/download-history")
async def add_download_history(payload: DownloadHistoryPayload):
    return await download_history_service.add_download_history_payload(payload, db_path=DB_PATH)
