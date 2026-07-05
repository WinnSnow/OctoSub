# -*- coding: utf-8 -*-
from cms_transfer_sync_service import (
    fetch_cms_share_down_records as _fetch_cms_share_down_records,
    get_cms_base_url as _get_cms_base_url,
    get_cms_share_down_list_url as _get_cms_share_down_list_url,
    map_cms_transfer_status as _map_cms_transfer_status,
    sync_cms_transfer_result_with_retries as _sync_cms_transfer_result_with_retries,
    sync_cms_transfer_results as _sync_cms_transfer_results,
)
from config import DB_PATH
from download_history_status import DOWNLOAD_STATUS_SUCCESS
from jellyfin_library_index_service import schedule_jellyfin_library_index_refresh
from subscription_transfer_confirmation_service import schedule_confirmations_for_successful_history_ids
from transfer_history_repository import (
    list_submitted_download_history_link_candidates,
    update_download_history_callback_for_ids,
)
from transfer_history_service import (
    queue_pending_transfer as _queue_pending_transfer,
    record_download_history as _record_download_history,
    reserve_download_history as _reserve_download_history,
)
from transfer_link_service import extract_115_share_code
from wecom_transfer_service import (
    ForwardTransferAlreadyExists as ForwardTransferAlreadyExists,
    ForwardTransferError as ForwardTransferError,
    decrypt_wecom_echo as _decrypt_wecom_echo,
    decrypt_wecom_message as _decrypt_wecom_message,
    extract_text_from_wecom_xml as _extract_text_from_wecom_xml,
    get_wecom_crypt as _get_wecom_crypt,
    parse_transfer_callback_message as _parse_transfer_callback_message,
    process_forward_link as _process_forward_link,
)


__all__ = [
    "ForwardTransferAlreadyExists",
    "ForwardTransferError",
    "apply_transfer_callback_result",
    "decrypt_wecom_echo",
    "decrypt_wecom_message",
    "extract_text_from_wecom_xml",
    "fetch_cms_share_down_records",
    "get_cms_base_url",
    "get_cms_share_down_list_url",
    "get_wecom_crypt",
    "map_cms_transfer_status",
    "parse_transfer_callback_message",
    "process_forward_link",
    "queue_pending_transfer",
    "record_download_history",
    "reserve_download_history",
    "sync_cms_transfer_result_with_retries",
    "sync_cms_transfer_results",
]


def get_wecom_crypt():
    return _get_wecom_crypt()


def decrypt_wecom_echo(echostr: str, msg_signature: str, timestamp: str, nonce: str) -> str:
    return _decrypt_wecom_echo(echostr, msg_signature, timestamp, nonce)


def decrypt_wecom_message(post_data: str, msg_signature: str, timestamp: str, nonce: str) -> str:
    return _decrypt_wecom_message(post_data, msg_signature, timestamp, nonce)


def extract_text_from_wecom_xml(plain_xml: str) -> str:
    return _extract_text_from_wecom_xml(plain_xml)


def parse_transfer_callback_message(text: str) -> dict | None:
    return _parse_transfer_callback_message(text)


def get_cms_base_url() -> str:
    return _get_cms_base_url()


def get_cms_share_down_list_url() -> str:
    return _get_cms_share_down_list_url()


def map_cms_transfer_status(record: dict) -> tuple[str, str] | None:
    return _map_cms_transfer_status(record)


async def apply_transfer_callback_result(result: dict) -> dict:
    link = result["link"]
    status = result["status"]
    message = result["message"]
    share_code = extract_115_share_code(link)
    candidate_rows = await list_submitted_download_history_link_candidates(
        link=link,
        share_code=share_code,
        db_path=DB_PATH,
    )
    updated_ids = [
        int(row[0])
        for row in candidate_rows
        if not share_code or row[1] == link or extract_115_share_code(row[1]) == share_code
    ]
    updated_count = await update_download_history_callback_for_ids(
        updated_ids,
        status=status,
        message=message,
        db_path=DB_PATH,
    )
    if status == DOWNLOAD_STATUS_SUCCESS and updated_count > 0:
        schedule_jellyfin_library_index_refresh("transfer_callback_success")
        await schedule_confirmations_for_successful_history_ids(updated_ids, DB_PATH)
    return {"matched": updated_count, "link": link, "share_code": share_code, "status": status}


async def fetch_cms_share_down_records(page_size: int | None = None) -> list[dict]:
    return await _fetch_cms_share_down_records(page_size)


async def sync_cms_transfer_results(limit: int = 100) -> dict:
    return await _sync_cms_transfer_results(limit, DB_PATH)


async def sync_cms_transfer_result_with_retries(
    history_id: int | None = None,
    *,
    fingerprint: str | None = None,
    attempts: int | None = None,
    delay_seconds: int | None = None,
) -> dict:
    kwargs = {}
    if attempts is not None:
        kwargs["attempts"] = attempts
    if delay_seconds is not None:
        kwargs["delay_seconds"] = delay_seconds
    return await _sync_cms_transfer_result_with_retries(history_id, fingerprint=fingerprint, db_path=DB_PATH, **kwargs)


def process_forward_link(link: str) -> str:
    return _process_forward_link(link)


async def record_download_history(
    subscription_id: int | None,
    fingerprint: str,
    link: str,
    status: str,
    message: str | None = None,
    title: str | None = None,
) -> None:
    await _record_download_history(subscription_id, fingerprint, link, status, message, title, DB_PATH)


async def reserve_download_history(
    subscription_id: int | None,
    fingerprint: str,
    link: str,
    title: str | None = None,
) -> tuple[bool, int | None]:
    return await _reserve_download_history(subscription_id, fingerprint, link, title, DB_PATH)


async def queue_pending_transfer(subscription_id: int | None, result: dict) -> dict:
    return await _queue_pending_transfer(subscription_id, result, DB_PATH)
