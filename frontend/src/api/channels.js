import apiClient from './client';

export const getChannels = () => apiClient.get('/api/channels');
export const getPublicChannels = () => apiClient.get('/api/public-channels');
export const addChannel = (payload) => apiClient.post('/api/channels', payload);
export const deleteChannel = (id) => apiClient.delete(`/api/channels/${id}`);
export const scrape = (payload) => apiClient.post('/api/scrape', payload);
export const retryMissingForChannel = (channelName) => apiClient.post(`/api/channels/${channelName}/retry_missing`);
