import apiClient from './client';

export const getSystemStatus = () => apiClient.get('/api/system/status');
export const cleanupSystemCache = (params) => apiClient.post('/api/system/cache/cleanup', null, { params });
