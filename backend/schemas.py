# -*- coding: utf-8 -*-
import re

from pydantic import BaseModel, field_validator

from utils import classify_resource_url, is_safe_external_url, normalize_channel_url


class Channel(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_channel_url(cls, value: str) -> str:
        normalized = normalize_channel_url(value)
        if not normalized:
            raise ValueError("无效的频道 URL 或用户名")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,64}", normalized):
            raise ValueError("频道用户名格式无效")
        return normalized


class ScrapeRequest(BaseModel):
    channel_name: str | None = None

    @field_validator("channel_name")
    @classmethod
    def validate_channel_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_channel_url(value)
        if not normalized or not re.fullmatch(r"[A-Za-z0-9_]{5,64}", normalized):
            raise ValueError("频道用户名格式无效")
        return normalized


class LinkPayload(BaseModel):
    link: str

    @field_validator("link")
    @classmethod
    def validate_link(cls, value: str) -> str:
        link = value.strip()
        if not is_safe_external_url(link, {"http", "https"}):
            raise ValueError("链接格式无效")
        if classify_resource_url(link) != "115":
            raise ValueError("仅允许转发 115 资源链接")
        return link


class TransferPayload(BaseModel):
    url: str
    password: str | None = None
    title: str | None = None
    result_id: str | None = None
    subscription_id: int | None = None
    auto: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        link = value.strip()
        if not is_safe_external_url(link, {"http", "https"}):
            raise ValueError("链接格式无效")
        if classify_resource_url(link) != "115":
            raise ValueError("仅允许转发 115 资源链接")
        return link


class SubscriptionPayload(BaseModel):
    keyword: str
    quality_filter: str | None = None
    media_type: str = "tv"
    tmdb_id: int | None = None
    tmdb_type: str | None = None
    year: int | None = None
    poster_url: str | None = None
    douban_id: str | None = None
    douban_url: str | None = None
    douban_rating: float | None = None
    metadata_source: str | None = None
    enabled: bool = True
    auto_transfer: bool = True
    min_confidence: float | None = None
    target_seasons: list[int] | None = None

    @field_validator("min_confidence")
    @classmethod
    def validate_min_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if value < 0 or value > 1:
            raise ValueError("自动转存置信度必须在 0 到 1 之间")
        return value

    @field_validator("target_seasons")
    @classmethod
    def validate_target_seasons(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        try:
            seasons = sorted({int(item) for item in value if int(item) > 0})
        except Exception as exc:
            raise ValueError("订阅季必须是正整数") from exc
        return seasons

    @field_validator("metadata_source")
    @classmethod
    def validate_metadata_source(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"tmdb", "douban", "manual"}:
            raise ValueError("元数据来源只能是 tmdb、douban 或 manual")
        return normalized


class SubscriptionLifecycleUpdate(BaseModel):
    status: str | None = None
    completion_reason: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"active", "completed", "paused"}:
            raise ValueError("订阅状态只能是 active、completed 或 paused")
        return normalized


class SubscriptionStatusUpdate(BaseModel):
    status: str
    enabled: bool | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"active", "completed", "paused"}:
            raise ValueError("订阅状态只能是 active、completed 或 paused")
        return normalized


class SubscriptionCheckRequest(BaseModel):
    subscription_id: int | None = None


class DownloadHistoryPayload(BaseModel):
    subscription_id: int | None = None
    title: str | None = None
    fingerprint: str
    link: str
    status: str = "success"


class FavoritePayload(BaseModel):
    item_key: str
    payload: dict


class RetryRequest(BaseModel):
    channel_name: str
    message_id: int


class SingleMatchRequest(BaseModel):
    message_id: int


class ProxyConfig(BaseModel):
    protocol: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    enabled: bool = True
    mode: str = "auto"

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        protocol = value.strip().lower()
        if protocol not in {"http", "socks4", "socks5"}:
            raise ValueError("代理协议只能是 http、socks4 或 socks5")
        return protocol

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        host = value.strip()
        if not host or any(ch in host for ch in "/:@?#"):
            raise ValueError("代理主机格式无效")
        return host

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("代理端口必须在 1-65535 之间")
        return value

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        mode = value.strip().lower()
        if mode not in {"auto", "manual", "direct"}:
            raise ValueError("代理模式只能是 auto、manual 或 direct")
        return mode


class ProxyStateUpdate(BaseModel):
    enabled: bool | None = None
    mode: str | None = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        mode = value.strip().lower()
        if mode not in {"auto", "manual", "direct"}:
            raise ValueError("代理模式只能是 auto、manual 或 direct")
        return mode


class ManualSearchRequest(BaseModel):
    query: str


class UpdatePosterRequest(BaseModel):
    message_id: int
    image_url: str
    tmdb_id: int | None = None
    tmdb_type: str | None = None
    year: int | None = None

    @field_validator("tmdb_type")
    @classmethod
    def validate_tmdb_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"movie", "tv"}:
            raise ValueError("TMDB 类型只能是 movie 或 tv")
        return normalized


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    phone: str = None
    code: str = None
    phone_code_hash: str = None
    password: str = None
