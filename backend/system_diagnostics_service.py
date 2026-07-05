# -*- coding: utf-8 -*-
from config import (
    ADMIN_PASSWORD,
    ADMIN_PASSWORD_HASH,
    API_HASH,
    API_ID,
    AUTH_SECRET_CONFIGURED,
    DOUBAN_API_CONFIGURED,
    DOUBAN_ENABLED,
    DOUBAN_LEGACY_DEFAULTS,
    PANSOU_BASE_URL,
    PANSOU_ENABLED,
    PUBLIC_SEARCH_CHANNELS,
)


def _configuration_item(
    key: str,
    label: str,
    configured: bool,
    *,
    required: bool,
    capability: str,
    hint: str,
    deprecated: bool = False,
) -> dict:
    return {
        "key": key,
        "label": label,
        "configured": bool(configured),
        "required": required,
        "capability": capability,
        "hint": hint,
        "deprecated": deprecated,
    }


def build_configuration_health(checks: dict) -> dict:
    auth_password_configured = bool(ADMIN_PASSWORD_HASH or ADMIN_PASSWORD)
    auth_secret_persistent = AUTH_SECRET_CONFIGURED
    proxy = checks.get("proxy", {})
    items = [
        _configuration_item(
            "auth",
            "后台登录",
            auth_password_configured and auth_secret_persistent,
            required=True,
            capability="系统登录和会话保持",
            hint="配置 ADMIN_PASSWORD_HASH 或 ADMIN_PASSWORD，并固定 AUTH_SECRET。",
        ),
        _configuration_item(
            "telegram_api",
            "Telegram API",
            bool(API_ID and API_HASH),
            required=True,
            capability="Telegram 登录、频道抓取和实时搜索",
            hint="配置 API_ID 和 API_HASH。",
        ),
        _configuration_item(
            "runtime_paths",
            "运行路径",
            checks.get("runtime_paths", {}).get("status") == "connected",
            required=True,
            capability="数据库、Session 和日志写入",
            hint="确保 runtime/data/session/log 目录存在且后端进程可写。",
        ),
        _configuration_item(
            "cms",
            "CMS 转存",
            bool(checks.get("cms", {}).get("configured")),
            required=False,
            capability="转存提交和 CMS 转存状态同步",
            hint="配置 CMS_BASE_URL、CMS_SHARE_DOWN_LIST_URL 或 FORWARD_URL。",
        ),
        _configuration_item(
            "tmdb",
            "TMDB",
            bool(checks.get("tmdb", {}).get("configured")),
            required=False,
            capability="海报墙、标题增强和订阅剧集完成度",
            hint="配置 TMDB_API_KEY。",
        ),
        _configuration_item(
            "jellyfin",
            "Jellyfin",
            bool(checks.get("jellyfin", {}).get("configured")),
            required=False,
            capability="媒体库去重和订阅完成度判断",
            hint="在 Jellyfin 设置页保存 URL 和 API Key，或配置环境变量。",
        ),
        _configuration_item(
            "proxy",
            "代理",
            bool(proxy.get("configured") or proxy.get("system_mode") == "direct"),
            required=False,
            capability="Telegram、TMDB 和公开搜索网络访问",
            hint="网络不稳定时，在代理设置中配置代理并切换系统模式。",
        ),
        _configuration_item(
            "pansou",
            "PanSou 搜索",
            bool(PANSOU_BASE_URL) or not PANSOU_ENABLED,
            required=False,
            capability="网盘搜索聚合结果",
            hint="启用 PanSou 时配置 PANSOU_BASE_URL；不用时可关闭 PANSOU_ENABLED。",
        ),
        _configuration_item(
            "douban",
            "豆瓣增强",
            bool(DOUBAN_API_CONFIGURED) or not DOUBAN_ENABLED,
            required=False,
            capability="豆瓣评分、详情和推荐增强",
            hint="配置 DOUBAN_API_KEY 和 DOUBAN_API_SECRET；未配置时可能使用兼容默认密钥，建议迁移为显式配置。",
            deprecated=bool(DOUBAN_LEGACY_DEFAULTS and DOUBAN_ENABLED),
        ),
        _configuration_item(
            "public_search_channels",
            "公开搜索频道",
            bool(PUBLIC_SEARCH_CHANNELS),
            required=False,
            capability="Telegram 公开频道搜索",
            hint="配置 PUBLIC_SEARCH_CHANNELS。",
        ),
    ]
    required_total = sum(1 for item in items if item["required"])
    required_ready = sum(1 for item in items if item["required"] and item["configured"])
    optional_total = len(items) - required_total
    optional_ready = sum(1 for item in items if not item["required"] and item["configured"])
    missing_required = [item["key"] for item in items if item["required"] and not item["configured"]]
    missing_optional = [item["key"] for item in items if not item["required"] and not item["configured"]]
    status = "connected" if not missing_required else "warning"
    return {
        "status": status,
        "message": f"必要配置 {required_ready}/{required_total}，增强配置 {optional_ready}/{optional_total}",
        "items": items,
        "required_total": required_total,
        "required_ready": required_ready,
        "optional_total": optional_total,
        "optional_ready": optional_ready,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }


def build_diagnostics(checks: dict) -> list[dict]:
    diagnostics = []
    configuration = checks.get("configuration", {})
    if configuration.get("missing_required"):
        diagnostics.append({
            "severity": "warning",
            "title": "必要配置未完成",
            "message": "后台登录、Telegram API 或运行路径缺失会影响核心能力。先处理配置健康中的必要项。",
            "target": "configuration",
        })

    deprecated_items = [item for item in configuration.get("items", []) if item.get("deprecated")]
    if deprecated_items:
        diagnostics.append({
            "severity": "info",
            "title": "存在兼容默认配置",
            "message": "部分增强能力正在使用兼容默认值。建议在 .env 中显式配置，避免后续版本移除默认值后行为变化。",
            "target": "configuration",
        })

    if checks.get("database", {}).get("status") == "disconnected":
        diagnostics.append({
            "severity": "danger",
            "title": "数据库不可访问",
            "message": "搜索、任务、订阅和转存历史都依赖数据库，优先检查 DB_PATH 和运行目录权限。",
            "target": "database",
        })

    telegram = checks.get("telegram", {})
    if telegram.get("status") != "connected":
        diagnostics.append({
            "severity": "warning",
            "title": "Telegram 未就绪",
            "message": "公开搜索仍可用，但频道抓取和登录态相关能力可能受影响。检查账号登录和代理设置。",
            "target": "telegram",
        })

    proxy = checks.get("proxy", {})
    if telegram.get("status") != "connected" and proxy.get("system_mode") == "direct":
        diagnostics.append({
            "severity": "info",
            "title": "可尝试启用代理",
            "message": "当前为直连模式。如果 Telegram 连接不稳定，可在代理设置中切换为自动或手动代理。",
            "target": "proxy",
        })

    jellyfin = checks.get("jellyfin", {})
    if jellyfin.get("configured") and not jellyfin.get("connected"):
        diagnostics.append({
            "severity": "warning",
            "title": "Jellyfin 已配置但连接失败",
            "message": "订阅去重和媒体库完成度判断可能不准确。检查 Jellyfin URL、API Key 和网络连通性。",
            "target": "jellyfin",
        })

    if not checks.get("cms", {}).get("configured"):
        diagnostics.append({
            "severity": "warning",
            "title": "CMS 未配置",
            "message": "转存提交和 CMS 结果同步不可用。配置 CMS_BASE_URL 或 FORWARD_URL 后再使用转存能力。",
            "target": "cms",
        })

    if not checks.get("tmdb", {}).get("configured"):
        diagnostics.append({
            "severity": "info",
            "title": "TMDB 未配置",
            "message": "海报墙、订阅剧集完成度和搜索增强能力会受限。配置 TMDB_API_KEY 可提升匹配准确度。",
            "target": "tmdb",
        })

    cache = checks.get("cache", {})
    if cache.get("expired", 0) > max(cache.get("active", 0), 0) and cache.get("expired", 0) > 0:
        diagnostics.append({
            "severity": "info",
            "title": "过期缓存较多",
            "message": "可在系统状态页清理过期缓存，减少缓存表体积。",
            "target": "cache",
        })

    failed_tasks = checks.get("recent_failed_tasks", {})
    if failed_tasks.get("total", 0) > 0:
        diagnostics.append({
            "severity": "warning",
            "title": "存在失败任务",
            "message": "查看任务中心的失败原因统计，并对可重试任务执行重试。",
            "target": "tasks",
        })

    runtime_paths = checks.get("runtime_paths", {})
    if runtime_paths.get("status") != "connected":
        diagnostics.append({
            "severity": "warning",
            "title": "运行路径存在异常",
            "message": "检查 runtime/data/session/log 目录是否存在且后端进程可写。",
            "target": "runtime_paths",
        })

    return diagnostics[:8]
