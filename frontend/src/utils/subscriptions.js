import { DEFAULT_SUBSCRIPTION_CONFIDENCE } from '../config/app';

export const SUBSCRIPTION_VIEW_FILTERS = [
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'all', label: '全部' },
];

export function getTmdbMediaType(type) {
  return type === '电影' ? 'movie' : 'tv';
}

export function getTmdbDisplayType(mediaType) {
  return mediaType === 'movie' ? '电影' : '剧集';
}

export function parseTmdbYear(year) {
  if (!year || year === '未知年份') return null;
  return parseInt(year, 10);
}

export function createEmptySubscriptionForm() {
  return {
    keyword: '',
    quality_filter: '',
    media_type: 'tv',
    tmdb_id: null,
    tmdb_type: null,
    year: null,
    poster_url: null,
    target_seasons: null,
    enabled: true,
    auto_transfer: true,
    min_confidence: DEFAULT_SUBSCRIPTION_CONFIDENCE,
  };
}

export function createSubscriptionFormFromTmdb(item, currentForm = createEmptySubscriptionForm()) {
  const mediaType = getTmdbMediaType(item.type);
  return {
    ...currentForm,
    keyword: item.title,
    media_type: mediaType,
    tmdb_id: item.id,
    tmdb_type: mediaType,
    year: parseTmdbYear(item.year),
    poster_url: item.poster_url,
    target_seasons: mediaType === 'tv' ? [] : null,
  };
}

export function createSubscriptionFormFromRecord(subscription) {
  return {
    keyword: subscription.keyword,
    quality_filter: subscription.quality_filter || '',
    media_type: subscription.media_type,
    tmdb_id: subscription.tmdb_id || null,
    tmdb_type: subscription.tmdb_type || null,
    year: subscription.year || null,
    poster_url: subscription.poster_url || null,
    target_seasons: subscription.target_seasons || null,
    enabled: subscription.enabled !== false,
    auto_transfer: subscription.auto_transfer !== false,
    min_confidence: subscription.min_confidence ?? DEFAULT_SUBSCRIPTION_CONFIDENCE,
  };
}

export function formatTargetSeasons(subscription) {
  if (subscription?.media_type !== 'tv') return '';
  const seasons = subscription?.target_seasons;
  if (!Array.isArray(seasons) || seasons.length === 0) return '订阅范围：未限定季';
  return `订阅范围：${seasons.map(season => `S${String(season).padStart(2, '0')}`).join('、')}`;
}

export function createSelectedTmdbFromSubscription(subscription) {
  if (!subscription.tmdb_id) return null;
  return {
    id: subscription.tmdb_id,
    title: subscription.keyword,
    year: subscription.year,
    type: getTmdbDisplayType(subscription.media_type),
    poster_url: subscription.poster_url,
  };
}

export function getSubscriptionStatus(subscription) {
  return subscription.status || (subscription.enabled === false ? 'paused' : 'active');
}

export function formatSubscriptionProgress(subscription) {
  const current = Number(subscription.progress_current || 0);
  const total = Number(subscription.progress_total || 0);
  const missing = total > 0 ? Math.max(total - current, 0) : 0;
  if (subscription.status === 'completed') {
    if (subscription.media_type === 'tv' && total > 1) return `已完成订阅，Jellyfin 已入库 ${current}/${total}`;
    return '已完成订阅，Jellyfin 已入库';
  }
  if (subscription.status === 'paused' || subscription.enabled === false) return '已停用，不参与定时检查';
  if (subscription.media_type === 'tv' && total > 0) return `Jellyfin 已入库 ${current}/${total}，缺失 ${missing} 集`;
  return '订阅中，等待 Jellyfin 或 PanSou 检查结果';
}

function compactEpisodeRanges(episodes) {
  const values = [...new Set((episodes || []).map(Number).filter(Number.isFinite))].sort((a, b) => a - b);
  const ranges = [];
  let start = null;
  let previous = null;
  for (const episode of values) {
    if (start === null) {
      start = episode;
      previous = episode;
      continue;
    }
    if (episode === previous + 1) {
      previous = episode;
      continue;
    }
    ranges.push([start, previous]);
    start = episode;
    previous = episode;
  }
  if (start !== null) ranges.push([start, previous]);
  return ranges;
}

function formatRange(range, season, showSeason) {
  const [start, end] = range;
  const prefix = showSeason ? `S${String(season).padStart(2, '0')}` : '';
  return start === end ? `${prefix}E${start}` : `${prefix}E${start}-E${end}`;
}

export function formatMissingEpisodeSummary(subscription, maxParts = 4) {
  return formatEpisodeMapSummary(subscription?.episode_state?.missing_episodes, '缺', maxParts);
}

export function formatHistoricalMissingSummary(subscription, maxParts = 4) {
  return formatEpisodeMapSummary(subscription?.episode_state?.historical_missing, '历史缺失', maxParts);
}

export function formatFutureMissingSummary(subscription, maxParts = 4) {
  return formatEpisodeMapSummary(subscription?.episode_state?.future_available_missing, '后续待追', maxParts);
}

export function formatAutoSearchTarget(subscription) {
  const target = subscription?.episode_state?.auto_search_target;
  if (!target?.episode) return '';
  const season = Number(target.season || 1);
  const episode = Number(target.episode);
  if (!Number.isFinite(episode)) return '';
  const showSeason = season !== 1;
  return `下次自动检查：${showSeason ? `S${String(season).padStart(2, '0')}` : ''}E${episode}`;
}

function formatEpisodeMapSummary(missingBySeason, label, maxParts = 4) {
  if (!missingBySeason || typeof missingBySeason !== 'object') return '';

  const seasons = Object.keys(missingBySeason)
    .map(Number)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (!seasons.length) return '';

  const showSeason = seasons.length > 1 || seasons.some(season => season !== 1);
  const parts = [];
  let totalMissing = 0;
  for (const season of seasons) {
    const episodes = missingBySeason[String(season)] || [];
    totalMissing += episodes.length;
    for (const range of compactEpisodeRanges(episodes)) {
      parts.push(formatRange(range, season, showSeason));
    }
  }
  if (!parts.length) return '';

  const visibleParts = parts.slice(0, maxParts);
  const hiddenCount = Math.max(totalMissing - visibleParts.reduce((sum, part) => {
    const match = part.match(/E(\d+)(?:-E(\d+))?$/);
    if (!match) return sum;
    const start = Number(match[1]);
    const end = Number(match[2] || match[1]);
    return sum + Math.max(end - start + 1, 1);
  }, 0), 0);
  return `${label} ${visibleParts.join('、')}${hiddenCount > 0 ? ` 等 ${totalMissing} 集` : ''}`;
}
