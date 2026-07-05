import apiClient from './client';

export const getJellyfinStatus = () => apiClient.get('/api/jellyfin/status');
export const getJellyfinConfig = () => apiClient.get('/api/jellyfin/config');
export const getJellyfinLibraryIndex = () => apiClient.get('/api/jellyfin/library-index');
export const saveJellyfinConfig = (payload) => apiClient.post('/api/jellyfin/config', payload);
export const testJellyfinConnection = (payload) => apiClient.post('/api/jellyfin/test', payload);
export const syncJellyfinLibrary = () => apiClient.post('/api/jellyfin/sync-library');
