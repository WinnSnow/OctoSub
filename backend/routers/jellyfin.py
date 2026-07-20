# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from jellyfin_library_index_service import get_jellyfin_library_index_summary, sync_jellyfin_library_index
from jellyfin_service import (
    ensure_jellyfin_client,
    get_jellyfin_config_payload,
    get_jellyfin_status_payload,
    save_jellyfin_config_values,
    test_jellyfin_config_payload,
)
from task_service import create_task, enqueue_heavy_task, run_task_with_status, update_task
from task_status import TASK_STATUS_QUEUED
from utils import safe_error_detail as _safe_error_detail


router = APIRouter()


@router.get("/api/jellyfin/status")
async def get_jellyfin_status():
    return await get_jellyfin_status_payload()


@router.post("/api/jellyfin/test")
async def test_jellyfin_connection(payload: dict | None = None):
    try:
        result = await test_jellyfin_config_payload(
            (payload or {}).get("url"),
            (payload or {}).get("api_key"),
        )
        if result.get("connected"):
            return result
        raise HTTPException(status_code=400, detail=result.get("message") or "连接失败")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_safe_error_detail("Jellyfin 连接错误")) from exc


@router.get("/api/jellyfin/config")
async def get_jellyfin_config():
    return await get_jellyfin_config_payload()


@router.get("/api/jellyfin/library-index")
async def get_jellyfin_library_index():
    return await get_jellyfin_library_index_summary()


@router.post("/api/jellyfin/sync-library")
async def sync_jellyfin_library():
    jellyfin = await ensure_jellyfin_client()
    if not jellyfin:
        raise HTTPException(status_code=400, detail="Jellyfin 未配置")

    task_id = create_task(
        "jellyfin_library_sync",
        "Jellyfin 媒体库同步",
        message="Jellyfin 媒体库索引同步任务排队中...",
        status=TASK_STATUS_QUEUED,
    )

    async def run_sync():
        await run_task_with_status(
            task_id,
            lambda: sync_jellyfin_library_index(
                jellyfin,
                update_progress=lambda **kwargs: update_task(task_id, **kwargs),
            ),
            success_message=lambda result: f"Jellyfin 媒体库同步完成：{result.get('total', 0)} 个项目",
            failure_message="Jellyfin 媒体库同步失败",
        )

    enqueue_heavy_task(task_id, run_sync)
    return {
        "task_id": task_id,
        "message": "Jellyfin 媒体库同步任务已加入后台队列",
        "status": TASK_STATUS_QUEUED,
    }


@router.post("/api/jellyfin/config")
async def save_jellyfin_config(payload: dict):
    url = payload.get("url", "").strip()
    api_key = payload.get("api_key", "").strip()

    if not url or not api_key:
        raise HTTPException(status_code=400, detail="URL 和 API Key 不能为空")
    await save_jellyfin_config_values(url, api_key)
    jellyfin = await ensure_jellyfin_client()
    connected = await jellyfin.test_connection() if jellyfin else False
    return {
        "success": True,
        "message": "配置已保存" + ("并连接成功" if connected else "，但连接测试失败"),
        "connected": connected,
    }
