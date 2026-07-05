import apiClient from './client';

export const getProxyConfig = () => apiClient.get('/api/proxy');
export const saveProxyConfig = (payload) => apiClient.post('/api/proxy', payload);
export const updateProxyState = (payload) => apiClient.patch('/api/proxy/state', payload);
export const testProxyConfig = (payload) => apiClient.post('/api/proxy/test', payload);
export const deleteProxyConfig = () => apiClient.delete('/api/proxy');
