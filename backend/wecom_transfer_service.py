# -*- coding: utf-8 -*-
import base64
import os
import random
import re
import socket
import struct
import time
import xml.etree.cElementTree as ET

import requests
from Crypto.Cipher import AES
from fastapi import HTTPException

from pkcs7encoder import PKCS7Encoder
from structured_logging import log_event
from utils import classify_resource_url, is_safe_external_url
from WXBizMsgCrypt import WXBizMsgCrypt


class ForwardTransferError(RuntimeError):
    pass


class ForwardTransferAlreadyExists(ForwardTransferError):
    pass


def get_wecom_crypt() -> WXBizMsgCrypt:
    wecom_token = os.getenv("WECOM_TOKEN")
    encoding_aes_key_str = os.getenv("WECOM_ENCODING_AES_KEY")
    corp_id = os.getenv("WECOM_CORP_ID")
    if not all([wecom_token, encoding_aes_key_str, corp_id]):
        raise RuntimeError("企业微信回调配置不完整，缺少 WECOM_TOKEN/WECOM_ENCODING_AES_KEY/WECOM_CORP_ID。")
    return WXBizMsgCrypt(wecom_token, encoding_aes_key_str, corp_id)


def decrypt_wecom_echo(echostr: str, msg_signature: str, timestamp: str, nonce: str) -> str:
    wxcpt = get_wecom_crypt()
    expected = wxcpt.get_signature(wxcpt.m_sToken, timestamp, nonce, echostr)
    if expected != msg_signature:
        raise HTTPException(status_code=403, detail="企业微信回调签名校验失败")

    ciphertext = base64.b64decode(echostr)
    plain = AES.new(wxcpt.key, AES.MODE_CBC, wxcpt.iv).decrypt(ciphertext)
    plain = PKCS7Encoder().decode(plain)
    content, receive_id = wxcpt.get_msg_content_and_receiveid(plain)
    if receive_id.decode("utf-8") != wxcpt.m_sReceiveId:
        raise HTTPException(status_code=403, detail="企业微信 CorpID 校验失败")
    return content.decode("utf-8")


def decrypt_wecom_message(post_data: str, msg_signature: str, timestamp: str, nonce: str) -> str:
    ret, plain_xml = get_wecom_crypt().DecryptMsg(post_data, msg_signature, timestamp, nonce)
    if ret != 0 or not plain_xml:
        raise HTTPException(status_code=403, detail=f"企业微信消息解密失败: {ret}")
    return plain_xml


def extract_text_from_wecom_xml(plain_xml: str) -> str:
    root = ET.fromstring(plain_xml)
    content = root.findtext("Content")
    return (content or "").strip()


def parse_transfer_callback_message(text: str) -> dict | None:
    if not text:
        return None

    link_match = re.search(r"https?://(?:115cdn\.com|115\.com)/s/[^\s<>\"]+", text)
    link = link_match.group(0).rstrip(".,，。;；") if link_match else None
    status = None
    if re.search(r"转存失败|失败", text):
        status = "skipped" if re.search(r"已经转存过|已转存过", text) else "failed"
    elif re.search(r"转存成功|成功", text):
        status = "success"

    if not link or not status:
        return None
    return {"link": link, "status": status, "message": text}


def process_forward_link(link: str) -> str:
    forward_url = os.getenv("FORWARD_URL")
    wecom_token = os.getenv("WECOM_TOKEN")
    encoding_aes_key_str = os.getenv("WECOM_ENCODING_AES_KEY")
    corp_id = os.getenv("WECOM_CORP_ID")

    if not all([forward_url, wecom_token, encoding_aes_key_str, corp_id]):
        raise RuntimeError("服务器配置不完整，缺少转发或企业微信相关的环境变量。")
    if not is_safe_external_url(forward_url, {"http", "https"}):
        raise RuntimeError("FORWARD_URL 配置无效。")
    if classify_resource_url(link) != "115":
        raise RuntimeError("仅允许转发 115 资源链接。")

    wxcpt = WXBizMsgCrypt(wecom_token, encoding_aes_key_str, corp_id)
    timestamp = str(int(time.time()))
    nonce = str(random.randint(10000000, 99999999))

    raw_xml_to_encrypt = f"""
    <xml>
        <ToUserName><![CDATA[{corp_id}]]></ToUserName>
        <FromUserName><![CDATA[tg_web_vivew]]></FromUserName>
        <CreateTime>{timestamp}</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{link}]]></Content>
    </xml>
    """.strip()

    raw_bytes = raw_xml_to_encrypt.encode("utf-8")
    packed_len = struct.pack("I", socket.htonl(len(raw_bytes)))
    text_to_encrypt = wxcpt.get_random_str() + packed_len + raw_bytes + corp_id.encode("utf-8")

    pkcs7 = PKCS7Encoder()
    padded_text = pkcs7.encode(text_to_encrypt)

    cryptor = AES.new(wxcpt.key, AES.MODE_CBC, wxcpt.iv)
    ciphertext = cryptor.encrypt(padded_text)
    encrypted_text_b64 = base64.b64encode(ciphertext).decode("utf-8")
    signature = wxcpt.get_signature(wecom_token, timestamp, nonce, encrypted_text_b64)

    separator = "&" if "?" in forward_url else "?"
    target_url = f"{forward_url}{separator}msg_signature={signature}&timestamp={timestamp}&nonce={nonce}"
    final_post_body_xml = f"""
    <xml>
        <ToUserName><![CDATA[{corp_id}]]></ToUserName>
        <Encrypt><![CDATA[{encrypted_text_b64}]]></Encrypt>
    </xml>
    """.strip()

    headers = {"Content-Type": "application/xml"}
    log_event("wecom.forward.request", resource_type="115")
    response = requests.post(target_url, data=final_post_body_xml.encode("utf-8"), headers=headers, timeout=30)
    response.raise_for_status()
    response_text = (response.text or "").strip()
    log_event(
        "wecom.forward.response",
        status_code=response.status_code,
        response_has_body=bool(response_text),
        response_length=len(response_text),
    )

    if "转存失败" in response_text or "失败" in response_text:
        if "已经转存过" in response_text or "已转存过" in response_text:
            raise ForwardTransferAlreadyExists(response_text)
        raise ForwardTransferError(response_text)

    log_event("wecom.forward.accepted")
    return response_text
