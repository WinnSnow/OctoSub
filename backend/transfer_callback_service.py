# -*- coding: utf-8 -*-
import os

from fastapi import BackgroundTasks, HTTPException, Response

from schemas import LinkPayload
from structured_logging import log_event
from transfer_service import (
    apply_transfer_callback_result,
    decrypt_wecom_echo,
    decrypt_wecom_message,
    extract_text_from_wecom_xml,
    parse_transfer_callback_message,
    process_forward_link,
)
from utils import classify_resource_url, safe_task_result_link


def _wecom_forward_configured() -> bool:
    return all([
        os.getenv("FORWARD_URL"),
        os.getenv("WECOM_TOKEN"),
        os.getenv("WECOM_ENCODING_AES_KEY"),
        os.getenv("WECOM_CORP_ID"),
    ])


async def forward_115_link_task(payload: LinkPayload, background_tasks: BackgroundTasks) -> dict:
    link = payload.link.strip()
    if not link:
        raise HTTPException(status_code=400, detail="资源链接不能为空。")
    if classify_resource_url(link) != "115":
        raise HTTPException(status_code=400, detail="仅允许转发 115 资源链接。")
    if not _wecom_forward_configured():
        raise HTTPException(status_code=500, detail="服务器配置不完整，缺少转发或企业微信相关的环境变量。")

    def sync_post_request(link: str):
        try:
            process_forward_link(link)
        except Exception as exc:
            log_event("transfer.forward_failed", "error", error=str(exc), link=safe_task_result_link(link))

    background_tasks.add_task(sync_post_request, link)
    return {"status": "submitted", "message": "转存任务已提交 CMS，等待最终结果。"}


def verify_wecom_callback_response(
    *,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> Response:
    return Response(
        content=decrypt_wecom_echo(echostr, msg_signature, timestamp, nonce),
        media_type="text/plain",
    )


async def receive_wecom_callback_response(
    *,
    post_data: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
) -> Response:
    plain_xml = decrypt_wecom_message(post_data, msg_signature, timestamp, nonce)
    text = extract_text_from_wecom_xml(plain_xml)
    result = parse_transfer_callback_message(text)
    if result:
        await apply_transfer_callback_result(result)
    return Response(content="success", media_type="text/plain")
