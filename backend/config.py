# -*- coding: utf-8 -*-
from dataclasses import dataclass
import os

from dotenv import load_dotenv

from structured_logging import log_event

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_DEVELOPMENT_AUTH_SECRET = "development-auth-secret-change-me"
LEGACY_DOUBAN_API_KEY = "0dad551ec0f84ed02907ff5c42e8ec70"
LEGACY_DOUBAN_API_SECRET = "bf7dddc7c9cfe6f7"


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    runtime_dir: str
    data_dir: str
    session_dir: str
    log_dir: str
    backend_lock_path: str
    api_id: int
    api_hash: str
    db_path: str
    session_name: str
    tmdb_api_key: str
    tmdb_search_timeout_seconds: int
    douban_enabled: bool
    douban_base_url: str
    douban_api_key: str
    douban_api_secret: str
    douban_api_configured: bool
    douban_legacy_defaults: bool
    douban_timeout_seconds: int
    douban_search_ttl_seconds: int
    douban_detail_ttl_seconds: int
    douban_recommendation_ttl_seconds: int
    admin_username: str
    admin_password_hash: str
    admin_password: str
    auth_secret: str
    auth_secret_configured: bool
    auth_cookie_name: str
    auth_ttl_seconds: int
    auth_cookie_secure: bool
    public_search_ttl_seconds: int
    public_search_timeout_seconds: int
    public_search_max_channels: int
    public_search_channels: list[str]
    pansou_base_url: str
    pansou_enabled: bool
    pansou_enabled_configured: bool
    pansou_timeout_seconds: int
    search_cache_ttl_seconds: int
    search_default_cloud_type: str
    subscription_default_min_confidence: float
    cms_base_url: str
    cms_share_down_list_url: str
    cms_transfer_poll_page_size: int
    cms_transfer_sync_retry_attempts: int
    cms_transfer_sync_retry_delay_seconds: int
    jellyfin_url: str
    jellyfin_api_key: str
    jellyfin_enabled: bool
    jellyfin_library_index_refresh_min_interval_seconds: int
    subscription_check_hour: int
    subscription_check_minute: int
    subscription_check_interval_seconds: int
    subscription_enabled: bool


def _env_int(name: str, default: str) -> int:
    raw_value = os.getenv(name, default)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        log_event("config.env_int.invalid", "warning", name=name, value=raw_value, default=default)
        return int(default)


def _env_float(name: str, default: str) -> float:
    raw_value = os.getenv(name, default)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        log_event("config.env_float.invalid", "warning", name=name, value=raw_value, default=default)
        return float(default)


def _env_path(name: str, default: str) -> str:
    return os.getenv(name) or default


def _is_production(value: str | None = None) -> bool:
    return (value or os.getenv("APP_ENV") or os.getenv("ENV") or "development").strip().lower() in {
        "prod",
        "production",
    }


def _resolve_runtime_dir(
    project_root: str,
    *,
    runtime_dir: str | None = None,
    data_dir: str | None = None,
    session_dir: str | None = None,
    log_dir: str | None = None,
) -> str:
    if runtime_dir:
        return runtime_dir
    for configured_dir in (data_dir, session_dir, log_dir):
        if configured_dir:
            return os.path.dirname(configured_dir)
    return os.path.join(project_root, "runtime")


DISABLED_PUBLIC_SEARCH_CHANNELS = {"tgsearchers6", "tgseachers6"}


def _normalize_channel_name(value: str) -> str:
    value = (value or "").strip()
    if value.startswith(("http://", "https://")):
        value = value.rstrip("/").split("/")[-1]
    if value.startswith("t.me/"):
        value = value.split("/", 1)[1]
    if value.startswith("@"):
        value = value[1:]
    return value.strip()


def _parse_public_search_channels(value: str) -> list[str]:
    channels = []
    for item in (value or "").split(","):
        channel = _normalize_channel_name(item)
        if not channel or channel.lower() in DISABLED_PUBLIC_SEARCH_CHANNELS:
            continue
        channels.append(channel)
    return channels


def load_settings() -> Settings:
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    runtime_dir = _resolve_runtime_dir(
        PROJECT_ROOT,
        runtime_dir=os.getenv("RUNTIME_DIR"),
        data_dir=os.getenv("DATA_DIR"),
        session_dir=os.getenv("SESSION_DIR"),
        log_dir=os.getenv("LOG_DIR"),
    )
    data_dir = _env_path("DATA_DIR", os.path.join(runtime_dir, "data"))
    session_dir = _env_path("SESSION_DIR", os.path.join(runtime_dir, "sessions"))
    log_dir = _env_path("LOG_DIR", os.path.join(runtime_dir, "logs"))
    auth_secret = os.getenv("AUTH_SECRET", "")
    auth_secret_configured = bool(auth_secret)
    if not auth_secret:
        auth_secret = DEFAULT_DEVELOPMENT_AUTH_SECRET
    jellyfin_url = os.getenv("JELLYFIN_URL", "")
    jellyfin_api_key = os.getenv("JELLYFIN_API_KEY", "")
    douban_api_key = os.getenv("DOUBAN_API_KEY", "")
    douban_api_secret = os.getenv("DOUBAN_API_SECRET", "")
    douban_api_configured = bool(douban_api_key and douban_api_secret)
    douban_legacy_defaults = False
    if not douban_api_key and not douban_api_secret:
        douban_api_key = LEGACY_DOUBAN_API_KEY
        douban_api_secret = LEGACY_DOUBAN_API_SECRET
        douban_legacy_defaults = True
    pansou_base_url = os.getenv("PANSOU_BASE_URL", "").rstrip("/")
    pansou_enabled_raw = os.getenv("PANSOU_ENABLED")
    pansou_enabled_configured = pansou_enabled_raw is not None
    pansou_enabled = (
        pansou_enabled_raw.lower() == "true"
        if pansou_enabled_configured
        else bool(pansou_base_url)
    )
    return Settings(
        runtime_dir=runtime_dir,
        data_dir=data_dir,
        session_dir=session_dir,
        log_dir=log_dir,
        backend_lock_path=_env_path("BACKEND_LOCK_PATH", os.path.join(runtime_dir, "backend.lock")),
        api_id=_env_int("API_ID", "0") if (os.getenv("API_ID", "0") or "0").isdigit() else 0,
        api_hash=os.getenv("API_HASH", ""),
        db_path=_env_path("DB_PATH", os.path.join(data_dir, "telegram_data.db")),
        session_name=_env_path("SESSION_NAME", os.path.join(session_dir, "anon_dev")),
        tmdb_api_key=os.getenv("TMDB_API_KEY", ""),
        tmdb_search_timeout_seconds=_env_int("TMDB_SEARCH_TIMEOUT_SECONDS", "8"),
        douban_enabled=os.getenv("DOUBAN_ENABLED", "true").lower() == "true",
        douban_base_url=os.getenv("DOUBAN_BASE_URL", "https://frodo.douban.com/api/v2").rstrip("/"),
        douban_api_key=douban_api_key,
        douban_api_secret=douban_api_secret,
        douban_api_configured=douban_api_configured,
        douban_legacy_defaults=douban_legacy_defaults,
        douban_timeout_seconds=_env_int("DOUBAN_TIMEOUT_SECONDS", "8"),
        douban_search_ttl_seconds=_env_int("DOUBAN_SEARCH_TTL_SECONDS", "21600"),
        douban_detail_ttl_seconds=_env_int("DOUBAN_DETAIL_TTL_SECONDS", "259200"),
        douban_recommendation_ttl_seconds=_env_int("DOUBAN_RECOMMENDATION_TTL_SECONDS", "43200"),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        auth_secret=auth_secret,
        auth_secret_configured=auth_secret_configured,
        auth_cookie_name=os.getenv("AUTH_COOKIE_NAME", "tg_web_auth"),
        auth_ttl_seconds=_env_int("AUTH_TTL_SECONDS", "43200"),
        auth_cookie_secure=os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true",
        public_search_ttl_seconds=_env_int("PUBLIC_SEARCH_TTL_SECONDS", "1200"),
        public_search_timeout_seconds=_env_int("PUBLIC_SEARCH_TIMEOUT_SECONDS", "8"),
        public_search_max_channels=_env_int("PUBLIC_SEARCH_MAX_CHANNELS", "12"),
        public_search_channels=_parse_public_search_channels(os.getenv("PUBLIC_SEARCH_CHANNELS", "")),
        pansou_base_url=pansou_base_url,
        pansou_enabled=pansou_enabled,
        pansou_enabled_configured=pansou_enabled_configured,
        pansou_timeout_seconds=_env_int("PANSOU_TIMEOUT_SECONDS", "12"),
        search_cache_ttl_seconds=_env_int("SEARCH_CACHE_TTL_SECONDS", "1800"),
        search_default_cloud_type=os.getenv("SEARCH_DEFAULT_CLOUD_TYPE", "115"),
        subscription_default_min_confidence=_env_float("SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE", "0.82"),
        cms_base_url=os.getenv("CMS_BASE_URL", "").rstrip("/"),
        cms_share_down_list_url=os.getenv("CMS_SHARE_DOWN_LIST_URL", "").strip(),
        cms_transfer_poll_page_size=_env_int("CMS_TRANSFER_POLL_PAGE_SIZE", "100"),
        cms_transfer_sync_retry_attempts=_env_int("CMS_TRANSFER_SYNC_RETRY_ATTEMPTS", "3"),
        cms_transfer_sync_retry_delay_seconds=_env_int("CMS_TRANSFER_SYNC_RETRY_DELAY_SECONDS", "20"),
        jellyfin_url=jellyfin_url,
        jellyfin_api_key=jellyfin_api_key,
        jellyfin_enabled=bool(jellyfin_url and jellyfin_api_key),
        jellyfin_library_index_refresh_min_interval_seconds=_env_int(
            "JELLYFIN_LIBRARY_INDEX_REFRESH_MIN_INTERVAL_SECONDS",
            "1800",
        ),
        subscription_check_hour=_env_int("SUBSCRIPTION_CHECK_HOUR", "2"),
        subscription_check_minute=_env_int("SUBSCRIPTION_CHECK_MINUTE", "0"),
        subscription_check_interval_seconds=_env_int("SUBSCRIPTION_CHECK_INTERVAL_SECONDS", "10800"),
        subscription_enabled=os.getenv("SUBSCRIPTION_ENABLED", "true").lower() == "true",
    )


SETTINGS = load_settings()
RUNTIME_DIR = SETTINGS.runtime_dir
DATA_DIR = SETTINGS.data_dir
SESSION_DIR = SETTINGS.session_dir
LOG_DIR = SETTINGS.log_dir
BACKEND_LOCK_PATH = SETTINGS.backend_lock_path
API_ID = SETTINGS.api_id
API_HASH = SETTINGS.api_hash
DB_PATH = SETTINGS.db_path
SESSION_NAME = SETTINGS.session_name
TMDB_API_KEY = SETTINGS.tmdb_api_key
TMDB_SEARCH_TIMEOUT_SECONDS = SETTINGS.tmdb_search_timeout_seconds
DOUBAN_ENABLED = SETTINGS.douban_enabled
DOUBAN_BASE_URL = SETTINGS.douban_base_url
DOUBAN_API_KEY = SETTINGS.douban_api_key
DOUBAN_API_SECRET = SETTINGS.douban_api_secret
DOUBAN_API_CONFIGURED = SETTINGS.douban_api_configured
DOUBAN_LEGACY_DEFAULTS = SETTINGS.douban_legacy_defaults
DOUBAN_TIMEOUT_SECONDS = SETTINGS.douban_timeout_seconds
DOUBAN_SEARCH_TTL_SECONDS = SETTINGS.douban_search_ttl_seconds
DOUBAN_DETAIL_TTL_SECONDS = SETTINGS.douban_detail_ttl_seconds
DOUBAN_RECOMMENDATION_TTL_SECONDS = SETTINGS.douban_recommendation_ttl_seconds
ADMIN_USERNAME = SETTINGS.admin_username
ADMIN_PASSWORD_HASH = SETTINGS.admin_password_hash
ADMIN_PASSWORD = SETTINGS.admin_password
AUTH_SECRET = SETTINGS.auth_secret
AUTH_SECRET_CONFIGURED = SETTINGS.auth_secret_configured
AUTH_COOKIE_NAME = SETTINGS.auth_cookie_name
AUTH_TTL_SECONDS = SETTINGS.auth_ttl_seconds
AUTH_COOKIE_SECURE = SETTINGS.auth_cookie_secure
PUBLIC_SEARCH_TTL_SECONDS = SETTINGS.public_search_ttl_seconds
PUBLIC_SEARCH_TIMEOUT_SECONDS = SETTINGS.public_search_timeout_seconds
PUBLIC_SEARCH_MAX_CHANNELS = SETTINGS.public_search_max_channels
PUBLIC_SEARCH_CHANNELS = SETTINGS.public_search_channels
PANSOU_BASE_URL = SETTINGS.pansou_base_url
PANSOU_ENABLED = SETTINGS.pansou_enabled
PANSOU_ENABLED_CONFIGURED = SETTINGS.pansou_enabled_configured
PANSOU_TIMEOUT_SECONDS = SETTINGS.pansou_timeout_seconds
SEARCH_CACHE_TTL_SECONDS = SETTINGS.search_cache_ttl_seconds
SEARCH_DEFAULT_CLOUD_TYPE = SETTINGS.search_default_cloud_type
SUBSCRIPTION_DEFAULT_MIN_CONFIDENCE = SETTINGS.subscription_default_min_confidence
CMS_BASE_URL = SETTINGS.cms_base_url
CMS_SHARE_DOWN_LIST_URL = SETTINGS.cms_share_down_list_url
CMS_TRANSFER_POLL_PAGE_SIZE = SETTINGS.cms_transfer_poll_page_size
CMS_TRANSFER_SYNC_RETRY_ATTEMPTS = SETTINGS.cms_transfer_sync_retry_attempts
CMS_TRANSFER_SYNC_RETRY_DELAY_SECONDS = SETTINGS.cms_transfer_sync_retry_delay_seconds
JELLYFIN_URL = SETTINGS.jellyfin_url
JELLYFIN_API_KEY = SETTINGS.jellyfin_api_key
JELLYFIN_ENABLED = SETTINGS.jellyfin_enabled
JELLYFIN_LIBRARY_INDEX_REFRESH_MIN_INTERVAL_SECONDS = SETTINGS.jellyfin_library_index_refresh_min_interval_seconds
SUBSCRIPTION_CHECK_HOUR = SETTINGS.subscription_check_hour
SUBSCRIPTION_CHECK_MINUTE = SETTINGS.subscription_check_minute
SUBSCRIPTION_CHECK_INTERVAL_SECONDS = SETTINGS.subscription_check_interval_seconds
SUBSCRIPTION_ENABLED = SETTINGS.subscription_enabled


def validate_runtime_configuration(*, production: bool | None = None) -> None:
    validate_settings(SETTINGS, production=production)


def warn_if_temporary_auth_secret(settings: Settings = SETTINGS) -> None:
    if not settings.auth_secret_configured:
        log_event("config.auth_secret.temporary", "warning", message="未配置 AUTH_SECRET，当前使用开发占位密钥，生产环境必须配置固定密钥。")


def validate_settings(settings: Settings, *, production: bool | None = None) -> None:
    is_production = _is_production() if production is None else production
    missing_required = []
    if is_production and not settings.auth_secret_configured:
        missing_required.append("AUTH_SECRET")
    if is_production and not settings.admin_password_hash:
        missing_required.append("ADMIN_PASSWORD_HASH")
    if is_production and settings.admin_password and not settings.admin_password_hash:
        missing_required.append("ADMIN_PASSWORD_HASH (production must not rely on ADMIN_PASSWORD)")
    if is_production and (not settings.api_id or not settings.api_hash):
        missing_required.append("API_ID/API_HASH")
    if settings.pansou_enabled and not settings.pansou_base_url:
        missing_required.append("PANSOU_BASE_URL")
    if bool(settings.jellyfin_url) != bool(settings.jellyfin_api_key):
        missing_required.append("JELLYFIN_URL/JELLYFIN_API_KEY")
    if missing_required:
        raise ConfigurationError("生产环境配置缺失: " + ", ".join(missing_required))


def ensure_runtime_dirs(settings: Settings = SETTINGS) -> None:
    for path in (settings.runtime_dir, settings.data_dir, settings.session_dir, settings.log_dir):
        os.makedirs(path, exist_ok=True)
