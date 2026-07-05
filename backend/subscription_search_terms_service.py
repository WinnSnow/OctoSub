# -*- coding: utf-8 -*-
import re

from utils import normalize_text


SUBSCRIPTION_FALLBACK_SEARCH_TERM_LIMIT = 16


def _strip_title_year(value: str) -> str:
    return re.sub(r"[\s（(]*(?:19|20)\d{2}[）)]?\s*$", "", value or "").strip()


def extract_subscription_title_aliases(keyword: str) -> list[str]:
    base = (keyword or "").strip()
    if not base:
        return []

    aliases = [base]
    for match in re.findall(r"[（(]([^（）()]{2,80})[）)]", base):
        alias = _strip_title_year(match.strip())
        if alias and not re.fullmatch(r"(?:19|20)\d{2}", alias):
            aliases.append(alias)

    outside_brackets = _strip_title_year(re.sub(r"[（(][^（）()]+[）)]", "", base))
    if outside_brackets:
        aliases.append(outside_brackets)

    for source in (base, outside_brackets):
        for part in re.split(r"\s*[\/／|｜]\s*", source):
            alias = _strip_title_year(re.sub(r"[（(][^（）()]+[）)]", "", part).strip())
            if alias:
                aliases.append(alias)

    normalized_aliases = []
    seen = set()
    for alias in aliases:
        alias = re.sub(r"\s+", " ", alias).strip(" -_·:：")
        key = normalize_text(alias)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        normalized_aliases.append(alias)
    return normalized_aliases[:6]


def build_subscription_search_terms(keyword: str, year: int | None = None, media_type: str | None = None) -> list[str]:
    """
    订阅搜索要比最终匹配略宽松：有些源带年份反而搜不到。
    最终入队/转存仍会用完整订阅名和年份做相关性校验。
    """
    base = (keyword or "").strip()
    if not base:
        return []
    terms = []
    aliases = extract_subscription_title_aliases(base)
    for index, alias in enumerate(aliases):
        if year:
            terms.append(f"{alias} {year}")
            if index == 0:
                terms.append(f"{alias}（{year}）")
                terms.append(f"{alias}({year})")
        terms.append(alias)

        short_title = re.split(r"[:：\-–—·]", alias, maxsplit=1)[0].strip()
        if short_title and short_title != alias and len(normalize_text(short_title)) >= 2:
            if year:
                terms.append(f"{short_title} {year}".strip())
            terms.append(short_title)

    deduped = list(dict.fromkeys(term for term in terms if term))
    return deduped[:SUBSCRIPTION_FALLBACK_SEARCH_TERM_LIMIT]


def _text_matches_target_episode(text: str, season: int | None, episode: int | None) -> bool:
    return episode_coverage_state(text, season, episode) == "matched"


def _add_range(ranges: list[dict], season: int | None, start: int, end: int, source: str, confidence: str = "explicit") -> None:
    if start <= 0 or end <= 0:
        return
    if end < start:
        start, end = end, start
    ranges.append({
        "season": int(season or 1),
        "start": int(start),
        "end": int(end),
        "source": source,
        "confidence": confidence,
    })


def extract_episode_coverage_ranges(text: str | None) -> list[dict]:
    value = text or ""
    ranges: list[dict] = []

    for match in re.finditer(r"\bS0?(\d{1,2})\s*E0?(\d{1,4})\s*[-–—~至到]\s*E?0?(\d{1,4})\b", value, re.IGNORECASE):
        _add_range(ranges, int(match.group(1)), int(match.group(2)), int(match.group(3)), "sxxexx_range")

    for match in re.finditer(r"\bS0?(\d{1,2})\s*E0?(\d{1,4})\b", value, re.IGNORECASE):
        _add_range(ranges, int(match.group(1)), int(match.group(2)), int(match.group(2)), "sxxexx")

    for match in re.finditer(r"第\s*(\d{1,2})\s*季[^\d]{0,12}?第?\s*0?(\d{1,4})\s*[-–—~至到]\s*0?(\d{1,4})\s*[集话話]?", value):
        _add_range(ranges, int(match.group(1)), int(match.group(2)), int(match.group(3)), "chinese_season_range")

    for match in re.finditer(r"第\s*(\d{1,2})\s*季.{0,16}?第\s*0?(\d{1,4})\s*[集话話]", value):
        _add_range(ranges, int(match.group(1)), int(match.group(2)), int(match.group(2)), "chinese_season_episode")

    for match in re.finditer(r"第\s*(\d{1,2})\s*季\s*0?(\d{1,4})\s*[-–—~至到]\s*0?(\d{1,4})(?!\d)", value):
        _add_range(ranges, int(match.group(1)), int(match.group(2)), int(match.group(3)), "chinese_season_compact_range")

    for match in re.finditer(r"(?:更新至|更至|更)\s*(?:第\s*)?0?(\d{1,4})\s*[集话話]?", value, re.IGNORECASE):
        _add_range(ranges, 1, 1, int(match.group(1)), "update_to", "continuous")

    for match in re.finditer(r"Season\s*0?(\d{1,2}).{0,16}?全\s*0?(\d{1,4})\s*[集话話]?", value, re.IGNORECASE):
        _add_range(ranges, int(match.group(1)), 1, int(match.group(2)), "season_full_count")

    for match in re.finditer(r"(?<!\d)0?(\d{1,4})\s*[集话話]\s*全|全\s*0?(\d{1,4})\s*[集话話]|0?(\d{1,4})\s*[集话話]全", value):
        count = next((int(group) for group in match.groups() if group), None)
        if count:
            _add_range(ranges, 1, 1, count, "full_count", "inferred")

    for match in re.finditer(r"(?<![更新至更第S\d])0?(\d{1,4})\s*[集话話](?!\d)", value, re.IGNORECASE):
        _add_range(ranges, 1, int(match.group(1)), int(match.group(1)), "plain_episode", "weak")

    if re.search(r"全集|合集|完结|Complete", value, re.IGNORECASE):
        for match in re.finditer(r"(?:\bS0?(\d{1,2})\b|第\s*(\d{1,2})\s*季|Season\s*0?(\d{1,2}))", value, re.IGNORECASE):
            season = next((int(group) for group in match.groups() if group), None)
            if season:
                _add_range(ranges, season, 1, 9999, "season_pack", "pack")

    deduped = []
    seen = set()
    for item in ranges:
        key = (item["season"], item["start"], item["end"], item["source"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def episode_coverage_state(text: str | None, season: int | None, episode: int | None) -> str:
    if not episode:
        return "not_required"
    target_season = int(season or 1)
    target_episode = int(episode)
    ranges = extract_episode_coverage_ranges(text)
    matched_other_season = False
    matched_other_episode_same_season = False
    ambiguous_pack = False
    for item in ranges:
        item_season = int(item.get("season") or 1)
        if item_season != target_season:
            matched_other_season = True
            continue
        if int(item["start"]) <= target_episode <= int(item["end"]):
            return "matched"
        if item.get("confidence") in {"pack", "inferred"} and item_season == target_season:
            ambiguous_pack = True
        else:
            matched_other_episode_same_season = True
    if ambiguous_pack:
        return "ambiguous"
    if matched_other_episode_same_season or matched_other_season:
        return "mismatch"
    if re.search(r"最新[一1]集|最新[一1]话|最新更新|连载中|持续更新|热更", text or "", re.IGNORECASE):
        return "ambiguous"
    return "ambiguous"


def result_matches_subscription_target(result: dict, target_season: int | None, target_episode: int | None) -> bool:
    if not target_episode:
        return True
    text = "\n".join([
        result.get("title") or "",
        result.get("description") or "",
        result.get("raw_text") or "",
        result.get("match_reason") or "",
    ])
    return _text_matches_target_episode(text, target_season, target_episode)


def build_missing_episode_term_targets(missing_episodes: list[dict]) -> dict[str, tuple[int | None, int | None]]:
    targets = {}
    for episode in missing_episodes:
        season_number = episode.get("season")
        episode_number = episode.get("episode")
        for term in episode.get("search_terms") or []:
            if term:
                targets[term] = (season_number, episode_number)
    return targets


def _combined_text(result: dict) -> str:
    return "\n".join([
        result.get("title") or "",
        result.get("description") or "",
        result.get("raw_text") or "",
        result.get("match_reason") or "",
    ])


def _title_text(result: dict) -> str:
    return "\n".join([
        result.get("title") or "",
        result.get("library_check_title") or "",
        result.get("search_keyword") or "",
    ])


def _has_subscription_title_match(text: str, keyword: str) -> bool:
    text_norm = normalize_text(text)
    keyword_norm = normalize_text(keyword)
    if not text_norm or not keyword_norm:
        return False
    if keyword_norm in text_norm:
        return True

    aliases = [alias for alias in extract_subscription_title_aliases(keyword) if normalize_text(alias) != keyword_norm]
    return any(normalize_text(alias) and normalize_text(alias) in text_norm for alias in aliases)


def movie_identity_match_state(
    result: dict,
    keyword: str,
    year: int | None = None,
    tmdb_id: int | None = None,
) -> str:
    """
    Movie subscriptions should not treat description-only mentions as media identity.
    Return values:
    - strong: title-side match, or requested TMDB id is present.
    - weak: only description/raw text mentions the title.
    - tmdb_mismatch: result declares a different TMDB id.
    - missing: no usable movie identity evidence.
    """
    result_tmdb_id = result.get("tmdb_id") or result.get("tmdbId")
    if tmdb_id and result_tmdb_id:
        try:
            if int(result_tmdb_id) != int(tmdb_id):
                return "tmdb_mismatch"
            return "strong"
        except (TypeError, ValueError):
            pass

    combined_text = _combined_text(result)
    if tmdb_id and str(tmdb_id) in combined_text:
        return "strong"

    if _has_subscription_title_match(_title_text(result), keyword):
        return "strong"

    if _has_subscription_title_match(combined_text, keyword):
        if year and str(year) in combined_text:
            return "weak"
        return "weak"
    return "missing"


def result_matches_movie_identity(
    result: dict,
    keyword: str,
    year: int | None = None,
    tmdb_id: int | None = None,
) -> bool:
    return movie_identity_match_state(result, keyword, year, tmdb_id) == "strong"
