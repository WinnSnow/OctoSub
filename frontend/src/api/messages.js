import apiClient from './client';

export const getMessages = (params) => apiClient.get('/api/messages', { params });
export const clearMessages = (payload) => apiClient.post('/api/messages/clear', payload);
export const retryMessage = (payload) => apiClient.post('/api/messages/retry', payload);
export const matchPosterSingle = (payload) => apiClient.post('/api/messages/match_poster_single', payload);
export const matchPosters = () => apiClient.post('/api/messages/match_posters');
export const updatePoster = (payload) => apiClient.post('/api/messages/update_poster', payload);
export const forward115Link = (payload) => apiClient.post('/api/forward_115_link', payload);
