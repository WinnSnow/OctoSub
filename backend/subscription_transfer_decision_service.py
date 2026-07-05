# -*- coding: utf-8 -*-
import asyncio
import re

from config import DB_PATH
from download_history_repository import download_history_exists_by_fingerprint_or_link
from download_history_status import DOWNLOAD_STATUS_FAILED, DOWNLOAD_STATUS_SKIPPED, DOWNLOAD_STATUS_SUBMITTED
from media_parser import match_quality_filter
from search_match_service import is_search_result_relevant
from structured_logging import log_event
from subscription_search_terms_service import (
    episode_coverage_state,
    extract_subscription_title_aliases,
    movie_identity_match_state,
)
from subscription_state_service import build_subscription_media_fingerprint
from title_utils import extract_episode_hint
from transfer_service import (
    ForwardTransferAlreadyExists,
    process_forward_link,
    queue_pending_transfer,
    record_download_history,
    reserve_download_history,
    sync_cms_transfer_result_with_retries,
)
from utils import classify_resource_url


def _empty_counts() -> dict[str, int]:
    return {"processed": 0, "submitted": 0, "skipped": 0, "pending": 0}


REVIEW_REASON_LABELS = {
    "manual_review": "人工审核",
    "missing_year": "年份缺失",
    "weak_title_match": "标题证据不足",
    "ambiguous_episode": "集数不明确",
    "weak_evidence": "证据不足",
    "low_confidence": "低于自动阈值",
    "safe_auto": "可自动转存",
}


def _combined_result_text(result: dict, fallback_title: str = "") -> str:
    return "\n".join([
        result.get("title") or fallback_title or "",
        result.get("description") or "",
        result.get("raw_text") or "",
        result.get("match_reason") or "",
    ])


def _text_has_year(text: str, year: int | None) -> bool:
    return not year or str(year) in (text or "")


def _text_has_tmdb_id(text: str, tmdb_id: int | None) -> bool:
    return bool(tmdb_id) and str(tmdb_id) in (text or "")


def _has_strong_episode_match(text: str, season: int | None, episode: int | None) -> bool:
    if not episode:
        return True
    value = text or ""
    if season and re.search(rf"\bS0?{season}\s*E0?{episode}\b", value, re.IGNORECASE):
        return True
    if season and re.search(rf"第\s*{season}\s*季.{{0,16}}?第\s*{episode}\s*[集话話]", value, re.IGNORECASE):
        return True
    return bool(re.search(rf"(?:\bEP?0?{episode}\b|第\s*{episode}\s*[集话話])", value, re.IGNORECASE))


def _update_to_episode_numbers(text: str) -> list[int]:
    numbers = []
    for match in re.finditer(r"(?:更新至|更至|更)\s*(?:第\s*)?0?(\d{1,4})\s*[集话話]?", text or "", re.IGNORECASE):
        try:
            numbers.append(int(match.group(1)))
        except ValueError:
            continue
    return numbers


def _update_to_episode_state(text: str, episode: int | None) -> str | None:
    if not episode:
        return None
    numbers = _update_to_episode_numbers(text)
    if not numbers:
        return None
    return "matched" if max(numbers) >= int(episode) else "mismatch"


def _has_explicit_other_episode(text: str, season: int | None, episode: int | None) -> bool:
    if not episode:
        return False
    value = text or ""
    patterns = [
        r"\bS0?(\d{1,2})\s*E0?(\d{1,4})\b",
        r"第\s*(\d{1,2})\s*季.{0,16}?第\s*(\d{1,4})\s*[集话話]",
        r"(?:\bEP?0?(\d{1,4})\b|第\s*(\d{1,4})\s*[集话話])",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, value, re.IGNORECASE):
            groups = [int(item) for item in match.groups() if item and item.isdigit()]
            if not groups:
                continue
            matched_episode = groups[-1]
            if any(number == matched_episode for number in _update_to_episode_numbers(match.group(0))):
                continue
            matched_season = groups[0] if len(groups) > 1 else season
            if matched_episode != int(episode) and (not season or not matched_season or int(matched_season) == int(season)):
                return True
    return False


def _has_ambiguous_episode_signal(text: str, episode: int | None) -> bool:
    if not episode:
        return False
    value = text or ""
    if re.search(r"最新[一1]集|最新[一1]话|最新更新|连载中|持续更新", value, re.IGNORECASE):
        return True
    if _update_to_episode_state(value, episode) == "matched":
        return True
    return False


def _episode_match_state(result: dict, season: int | None, episode: int | None, title: str) -> str:
    if not episode:
        return "not_required"
    text = _combined_result_text(result, title)
    coverage_state = episode_coverage_state(text, season, episode)
    if coverage_state in {"matched", "mismatch"}:
        return coverage_state
    if _has_strong_episode_match(text, season, episode):
        return "matched"
    update_state = _update_to_episode_state(text, episode)
    if update_state:
        return update_state
    if _has_explicit_other_episode(text, season, episode):
        return "mismatch"
    if _has_ambiguous_episode_signal(text, episode):
        return "ambiguous"
    return "ambiguous"


def _title_match_state(result: dict, keyword: str, title: str) -> str:
    title_text = title or result.get("title") or ""
    title_norm = _normalize(title_text)
    keyword_norm = _normalize(keyword)
    if keyword_norm and keyword_norm in title_norm:
        return "full"

    aliases = [alias for alias in extract_subscription_title_aliases(keyword) if _normalize(alias) != keyword_norm]
    if any(_normalize(alias) and _normalize(alias) in title_norm for alias in aliases):
        return "alias"

    tokens = [_normalize(part) for part in re.split(r"[\s:：·\-_–—]+", keyword or "") if _normalize(part)]
    meaningful = [token for token in tokens if len(token) >= 2 and not token.isdigit()]
    if meaningful and title_norm and all(token in title_norm for token in meaningful):
        return "partial"

    description_norm = _normalize("\n".join([result.get("description") or "", result.get("raw_text") or ""]))
    if keyword_norm and keyword_norm in description_norm:
        return "description"
    if meaningful and description_norm and all(token in description_norm for token in meaningful):
        return "description"
    return "none"


def _normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", (value or "").lower(), flags=re.UNICODE)


def _review_payload(
    *,
    action: str,
    reason: str,
    evidence: dict,
    risk_flags: list[str],
) -> dict:
    return {
        "action": action,
        "reason": reason,
        "reason_label": REVIEW_REASON_LABELS.get(reason, "需要审核"),
        "evidence": evidence,
        "risk_flags": risk_flags,
    }


def _identity_match_state(result: dict, subscription_year: int | None, subscription_tmdb_id: int | None, text: str) -> str:
    if _text_has_tmdb_id(text, subscription_tmdb_id):
        return "tmdb"
    if _text_has_year(text, subscription_year):
        return "year" if subscription_year else "not_required"
    return "missing"


def _build_subscription_fingerprint(
    *,
    subscription_id: int,
    keyword: str,
    subscription_year: int | None,
    media_type: str,
    tmdb_type: str | None,
    tmdb_id: int | None = None,
    title: str,
    link_url: str,
    target_season: int | None,
    target_episode: int | None,
    episode_state: str,
) -> tuple[dict, str]:
    parsed, fingerprint = build_subscription_media_fingerprint(
        subscription_id,
        keyword,
        subscription_year,
        tmdb_type or media_type,
        title,
        link_url,
    )
    if media_type == "tv" and target_episode and episode_state == "matched":
        parsed = dict(parsed or {})
        parsed.update({
            "title": keyword,
            "type": "episode",
            "season": target_season or parsed.get("season") or 1,
            "episode": target_episode,
            "year": parsed.get("year") or subscription_year,
        })
        fingerprint = f"{subscription_id}:{_normalize(keyword)}:S{int(parsed['season']):02d}E{int(target_episode):02d}"
    return parsed, fingerprint


def build_transfer_review_decision(
    result: dict,
    subscription_context: dict,
    parsed: dict | None,
    confidence: float,
) -> dict:
    title = result.get("title") or subscription_context.get("keyword") or ""
    keyword = subscription_context.get("keyword") or ""
    subscription_year = subscription_context.get("subscription_year")
    media_type = subscription_context.get("media_type")
    subscription_tmdb_id = subscription_context.get("tmdb_id")
    auto_transfer = bool(subscription_context.get("auto_transfer"))
    min_confidence = float(subscription_context.get("min_confidence") or 0)
    target_season = subscription_context.get("target_season")
    target_episode = subscription_context.get("target_episode")

    text = _combined_result_text(result, title)
    title_match = _title_match_state(result, keyword, title)
    year_match = "not_required" if not subscription_year else ("matched" if _text_has_year(text, subscription_year) else "missing")
    identity_match = _identity_match_state(result, subscription_year, subscription_tmdb_id, text)
    episode_match = _episode_match_state(result, target_season, target_episode, title) if media_type == "tv" else "not_required"
    match_reason = result.get("match_reason") or ""
    evidence = {
        "title_match": title_match,
        "year_match": year_match,
        "identity_match": identity_match,
        "episode_match": episode_match,
        "quality_match": True,
        "confidence": confidence,
        "min_confidence": min_confidence,
        "match_reason": match_reason,
        "parsed_type": (parsed or {}).get("type"),
    }

    risk_flags: list[str] = []
    if identity_match == "missing":
        risk_flags.append("年份/TMDB缺失")
    if episode_match == "ambiguous":
        risk_flags.append("集数不明确")
    if title_match in {"alias", "partial", "description", "none"}:
        risk_flags.append("标题证据不足")
    if not match_reason or match_reason == "基础匹配":
        risk_flags.append("匹配证据较弱")
    if confidence < min_confidence:
        risk_flags.append("低于自动阈值")

    reason = "safe_auto"
    if not auto_transfer:
        reason = "manual_review"
    elif identity_match == "missing":
        reason = "missing_year"
    elif episode_match == "ambiguous":
        reason = "ambiguous_episode"
    elif title_match in {"alias", "partial", "description", "none"}:
        reason = "weak_title_match"
    elif not match_reason or match_reason == "基础匹配":
        reason = "weak_evidence"
    elif confidence < min_confidence:
        reason = "low_confidence"

    action = "auto_transfer" if reason == "safe_auto" and confidence >= min_confidence else "review"
    return _review_payload(action=action, reason=reason, evidence=evidence, risk_flags=risk_flags)


async def _download_history_exists(fingerprint: str, link_url: str) -> bool:
    return await download_history_exists_by_fingerprint_or_link(fingerprint, link_url, db_path=DB_PATH)


async def _skip_if_jellyfin_has_media(
    jellyfin,
    parsed: dict,
    *,
    subscription_id: int,
    fingerprint: str,
    link_url: str,
    title: str,
) -> bool:
    if not jellyfin:
        return False

    if parsed.get("type") == "episode":
        season = parsed.get("season")
        episode = parsed.get("episode")
        hint_season, hint_episode = extract_episode_hint(title)
        season = season or hint_season
        episode = episode or hint_episode
        series_name = parsed.get("title")
        year = parsed.get("year")

        if not season or not episode:
            return False
        try:
            exists = await jellyfin.check_episode_exists(series_name, season, episode, year)
        except Exception as exc:
            log_event(
                "subscription.transfer.jellyfin_check_failed",
                "warning",
                subscription_id=subscription_id,
                media_type="episode",
                error_type=type(exc).__name__,
            )
            return False
        if exists:
            log_event(
                "subscription.transfer.skipped",
                subscription_id=subscription_id,
                reason="jellyfin_exists",
                media_type="episode",
                season=season,
                episode=episode,
            )
            await record_download_history(subscription_id, fingerprint, link_url, DOWNLOAD_STATUS_SKIPPED, title=title)
            return True
        return False

    if parsed.get("type") == "movie":
        movie_name = parsed.get("title")
        year = parsed.get("year")
        try:
            exists = await jellyfin.check_movie_exists(movie_name, year)
        except Exception as exc:
            log_event(
                "subscription.transfer.jellyfin_check_failed",
                "warning",
                subscription_id=subscription_id,
                media_type="movie",
                error_type=type(exc).__name__,
            )
            return False
        if exists:
            log_event(
                "subscription.transfer.skipped",
                subscription_id=subscription_id,
                reason="jellyfin_exists",
                media_type="movie",
                year=year,
            )
            await record_download_history(subscription_id, fingerprint, link_url, DOWNLOAD_STATUS_SKIPPED, title=title)
            return True
    return False


async def process_subscription_result(
    result: dict,
    *,
    subscription_id: int,
    keyword: str,
    subscription_year: int | None,
    media_type: str,
    tmdb_type: str | None,
    quality_filter: str | None,
    auto_transfer: bool,
    min_confidence: float,
    jellyfin,
    seen_result_links: set[str],
    seen_media_fingerprints: set[str],
    tmdb_id: int | None = None,
) -> dict[str, int]:
    counts = _empty_counts()
    link_url = result.get("resource_url") or result.get("url")
    if not link_url or link_url in seen_result_links:
        return counts
    seen_result_links.add(link_url)

    title = result.get("title") or keyword
    relevance_text = "\n".join([
        title,
        result.get("description") or "",
        result.get("raw_text") or "",
    ])
    if not is_search_result_relevant(relevance_text, keyword):
        log_event("subscription.transfer.skipped", subscription_id=subscription_id, reason="keyword_mismatch")
        counts["skipped"] += 1
        return counts

    target_season = result.get("_target_season")
    target_episode = result.get("_target_episode")
    episode_state = _episode_match_state(result, target_season, target_episode, title)
    if target_episode and episode_state == "mismatch":
        log_event(
            "subscription.transfer.skipped",
            subscription_id=subscription_id,
            reason="target_episode_mismatch",
            target_season=target_season,
            target_episode=target_episode,
        )
        counts["skipped"] += 1
        return counts
    if media_type == "movie":
        movie_match = movie_identity_match_state(result, keyword, subscription_year, tmdb_id)
        if movie_match != "strong":
            log_event(
                "subscription.transfer.skipped",
                subscription_id=subscription_id,
                reason="movie_identity_mismatch",
                match_state=movie_match,
            )
            counts["skipped"] += 1
            return counts

    counts["processed"] += 1
    parsed, fingerprint = _build_subscription_fingerprint(
        subscription_id=subscription_id,
        keyword=keyword,
        subscription_year=subscription_year,
        media_type=media_type,
        tmdb_type=tmdb_type,
        title=title,
        link_url=link_url,
        target_season=target_season,
        target_episode=target_episode,
        episode_state=episode_state,
    )
    if fingerprint in seen_media_fingerprints:
        log_event("subscription.transfer.skipped", subscription_id=subscription_id, reason="duplicate_media", fingerprint=fingerprint)
        counts["skipped"] += 1
        return counts

    if classify_resource_url(link_url) != "115":
        log_event("subscription.transfer.skipped", subscription_id=subscription_id, reason="non_115_link")
        return counts

    if not match_quality_filter(title, quality_filter):
        log_event("subscription.transfer.skipped", subscription_id=subscription_id, reason="quality_mismatch")
        return counts

    if await _download_history_exists(fingerprint, link_url):
        log_event("subscription.transfer.skipped", subscription_id=subscription_id, reason="download_history_exists", fingerprint=fingerprint)
        seen_media_fingerprints.add(fingerprint)
        counts["skipped"] += 1
        return counts

    if await _skip_if_jellyfin_has_media(
        jellyfin,
        parsed,
        subscription_id=subscription_id,
        fingerprint=fingerprint,
        link_url=link_url,
        title=title,
    ):
        seen_media_fingerprints.add(fingerprint)
        counts["skipped"] += 1
        return counts

    confidence = float(result.get("confidence") or 0)
    review_decision = build_transfer_review_decision(
        result,
        {
            "keyword": keyword,
            "subscription_year": subscription_year,
            "media_type": media_type,
            "tmdb_type": tmdb_type,
            "tmdb_id": tmdb_id or result.get("tmdb_id"),
            "target_season": target_season,
            "target_episode": target_episode,
            "auto_transfer": auto_transfer,
            "min_confidence": min_confidence,
            "quality_filter": quality_filter,
        },
        parsed,
        confidence,
    )

    if review_decision["action"] == "auto_transfer":
        reserved, history_id = await reserve_download_history(subscription_id, fingerprint, link_url, title)
        if not reserved:
            log_event("subscription.transfer.skipped", subscription_id=subscription_id, reason="transfer_already_reserved", fingerprint=fingerprint)
            seen_media_fingerprints.add(fingerprint)
            counts["skipped"] += 1
            return counts
        try:
            log_event(
                "subscription.transfer.auto_submitted",
                subscription_id=subscription_id,
                fingerprint=fingerprint,
                confidence=confidence,
            )
            response_text = await asyncio.to_thread(process_forward_link, link_url)
            message = response_text or "CMS 已接收转存任务，等待 115 最终结果"
            await record_download_history(subscription_id, fingerprint, link_url, DOWNLOAD_STATUS_SUBMITTED, message, title)
            sync_result = await sync_cms_transfer_result_with_retries(history_id, fingerprint=fingerprint)
            seen_media_fingerprints.add(fingerprint)
            counts["submitted"] += 1
            if sync_result.get("updated") and sync_result.get("status") != DOWNLOAD_STATUS_FAILED:
                log_event(
                    "subscription.transfer.cms_sync_updated",
                    subscription_id=subscription_id,
                    fingerprint=fingerprint,
                    status=sync_result.get("status"),
                )
            else:
                log_event("subscription.transfer.cms_sync_not_updated", "warning", subscription_id=subscription_id, fingerprint=fingerprint)
        except ForwardTransferAlreadyExists as exc:
            log_event(
                "subscription.transfer.skipped",
                subscription_id=subscription_id,
                reason="target_already_exists",
                fingerprint=fingerprint,
                error_type=type(exc).__name__,
            )
            await record_download_history(subscription_id, fingerprint, link_url, DOWNLOAD_STATUS_SKIPPED, title=title)
            seen_media_fingerprints.add(fingerprint)
            counts["skipped"] += 1
        except Exception as exc:
            log_event(
                "subscription.transfer.failed",
                "warning",
                subscription_id=subscription_id,
                fingerprint=fingerprint,
                error_type=type(exc).__name__,
            )
            await record_download_history(subscription_id, fingerprint, link_url, DOWNLOAD_STATUS_FAILED, title=title)
            seen_media_fingerprints.add(fingerprint)
        return counts

    pending_result = dict(result)
    pending_result["_review"] = review_decision
    queue_result = await queue_pending_transfer(subscription_id, pending_result)
    seen_media_fingerprints.add(fingerprint)
    if queue_result.get("inserted"):
        log_event(
            "subscription.transfer.pending_queued",
            subscription_id=subscription_id,
            fingerprint=fingerprint,
            reason=review_decision.get("reason"),
        )
        counts["pending"] += 1
    else:
        existing_status = queue_result.get("existing_status") or "unknown"
        log_event(
            "subscription.transfer.skipped",
            subscription_id=subscription_id,
            reason="pending_transfer_exists",
            fingerprint=fingerprint,
            existing_status=existing_status,
        )
        counts["skipped"] += 1
    return counts
