import apiClient from './client';

export const getCurrentUser = () => apiClient.get('/api/auth/me');
export const login = (credentials) => apiClient.post('/api/auth/login', credentials);
export const logout = () => apiClient.post('/api/auth/logout');
