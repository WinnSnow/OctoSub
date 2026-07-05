import apiClient from './client';

export const getTelegramStatus = () => apiClient.get('/api/telegram/status');
export const sendTelegramCode = (payload) => apiClient.post('/api/telegram/login/send-code', payload);
export const verifyTelegramCode = (payload) => apiClient.post('/api/telegram/login/verify-code', payload);
export const verifyTelegramPassword = (payload) => apiClient.post('/api/telegram/login/verify-password', payload);
export const logoutTelegram = () => apiClient.post('/api/telegram/logout');
export const resetTelegramSession = () => apiClient.post('/api/telegram/reset-session');
