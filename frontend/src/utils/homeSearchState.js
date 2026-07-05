import { HOME_LOCAL_PAGE_SIZE } from '../config/app';
import { normalizeSearchResult } from './home';
import { attachLibraryStateKeys } from './homeLibraryState';

export function buildPublicSearchParams({
  keyword,
  cloudTypes,
  forceRefresh = false,
  searchContext = null,
  selectedChannels = [],
}) {
  const params = {
    keyword,
    cloud_type: cloudTypes,
  };
  if (forceRefresh) params.force_refresh = true;
  if (searchContext?.keyword === keyword) {
    if (searchContext.tmdb_id) params.tmdb_id = searchContext.tmdb_id;
    if (searchContext.tmdb_type) params.tmdb_type = searchContext.tmdb_type;
    if (searchContext.year) params.year = searchContext.year;
  }
  if (selectedChannels.length > 0) params.channels = selectedChannels;
  return params;
}

export function createPublicSearchState(data) {
  const results = attachLibraryStateKeys((data.results || []).map(normalizeSearchResult));
  const total = data.total || 0;
  const searchMeta = {
    source: data.source,
    elapsed_ms: data.elapsed_ms,
    failed_channels: data.failed_channels || data.failed_sources || [],
    filters: data.filters,
    cached: data.cached,
  };
  return { results, total, searchMeta };
}

export function buildLocalSearchParams({
  keyword,
  page,
  localChannels = [],
}) {
  const params = { page, limit: HOME_LOCAL_PAGE_SIZE };
  if (keyword) params.search = keyword;
  if (localChannels.length > 0) params.channel_names = localChannels;
  return params;
}

export function createLocalSearchState({
  data,
  requestedPage,
  startedAt,
  keyword,
  localChannels = [],
}) {
  const results = attachLibraryStateKeys((data.messages || []).map(normalizeSearchResult));
  const total = data.total || 0;
  const localSources = data.sources || [];
  const page = Math.max(1, data.page || requestedPage);
  const searchMeta = {
    source: 'local_library',
    elapsed_ms: Math.round(performance.now() - startedAt),
    failed_channels: [],
    filters: { keyword, channels: localChannels },
    cached: false,
    limit: data.limit,
  };
  return { results, total, localSources, page, searchMeta };
}
