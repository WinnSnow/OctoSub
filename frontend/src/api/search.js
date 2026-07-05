import apiClient from './client';

export const getPosterWall = (category, options = {}) => apiClient.get('/api/poster-wall', {
  params: {
    category,
    ...options,
  },
});
export const searchResources = (params) => apiClient.get('/api/search', { params });
export const getLibraryStates = (payload) => apiClient.post('/api/library-states', payload);
export const searchTmdb = (query) => apiClient.post('/api/tmdb/search', { query });
export const searchMedia = (keyword, mediaType = null) => apiClient.get('/api/media/search', {
  params: {
    keyword,
    ...(mediaType ? { media_type: mediaType } : {}),
  },
});
export const searchDouban = (keyword, mediaType = null) => apiClient.get('/api/douban/search', {
  params: {
    keyword,
    ...(mediaType ? { media_type: mediaType } : {}),
  },
});
export const getDoubanDetail = (doubanId, mediaType = null) => apiClient.get(`/api/douban/${doubanId}`, {
  params: {
    ...(mediaType ? { media_type: mediaType } : {}),
  },
});
export const getTmdbDetail = (mediaType, tmdbId) => apiClient.get(`/api/tmdb/${mediaType}/${tmdbId}`);
export const getTmdbTvDetail = (tmdbId) => apiClient.get(`/api/tmdb/tv/${tmdbId}`);
