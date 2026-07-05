from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from config import DB_PATH
from pending_transfer_status import PENDING_TRANSFER_STATUS_PENDING
from schemas import LinkPayload, TransferPayload
import transfer_callback_service
import transfer_router_service
from subscription_transfer_confirmation_service import (
    resolve_library_missing_review,
)


router = APIRouter()
PENDING_REASON_LABELS = transfer_router_service.PENDING_REASON_LABELS
_extract_pending_review = transfer_router_service.extract_pending_review
_payload_text = transfer_router_service.payload_text
_load_pending_payload_json = transfer_router_service.load_pending_payload_json


@router.post("/api/forward_115_link")
async def forward_115_link(payload: LinkPayload, background_tasks: BackgroundTasks):
    return await transfer_callback_service.forward_115_link_task(payload, background_tasks)


@router.get("/api/wecom/callback")
async def verify_wecom_callback(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    return transfer_callback_service.verify_wecom_callback_response(
        msg_signature=msg_signature,
        timestamp=timestamp,
        nonce=nonce,
        echostr=echostr,
    )


@router.post("/api/wecom/callback")
async def receive_wecom_callback(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    post_data = (await request.body()).decode("utf-8")
    return await transfer_callback_service.receive_wecom_callback_response(
        post_data=post_data,
        msg_signature=msg_signature,
        timestamp=timestamp,
        nonce=nonce,
    )


@router.post("/api/transfer")
async def transfer_resource(payload: TransferPayload, background_tasks: BackgroundTasks):
    return await transfer_router_service.transfer_resource_task(payload, background_tasks)


@router.get("/api/pending-transfers")
async def get_pending_transfers(
    status: str = PENDING_TRANSFER_STATUS_PENDING,
    subscription_id: int | None = None,
    reason: str | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    sort: str = "latest",
    limit: int = 100,
):
    return await transfer_router_service.get_pending_transfers_payload(
        status=status,
        subscription_id=subscription_id,
        reason=reason,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        sort=sort,
        limit=limit,
        db_path=DB_PATH,
    )


@router.post("/api/pending-transfers/{pending_id}/approve")
async def approve_pending_transfer(pending_id: int, background_tasks: BackgroundTasks):
    return await transfer_router_service.approve_pending_transfer_task(pending_id, background_tasks, db_path=DB_PATH)


@router.post("/api/pending-transfers/{pending_id}/confirm-library")
async def confirm_pending_transfer_library(pending_id: int):
    result = await resolve_library_missing_review(pending_id, DB_PATH)
    if result.get("resolved"):
        return {"status": "success", "message": "已确认入库，订阅状态已同步", **result}
    if result.get("error") == "episode_not_found":
        raise HTTPException(status_code=409, detail="Jellyfin 仍未检测到目标集数，未更新订阅状态。")
    if result.get("error") == "not_library_missing_review":
        raise HTTPException(status_code=400, detail="该记录不是入库异常审核项。")
    raise HTTPException(status_code=404, detail="入库异常审核项不存在或已处理")


@router.post("/api/pending-transfers/{pending_id}/reject")
async def reject_pending_transfer(pending_id: int):
    return await transfer_router_service.reject_pending_transfer_task(pending_id, db_path=DB_PATH)
