import apiClient from './client';

export const getTask = (taskId) => apiClient.get(`/api/tasks/${taskId}`);
export const getTasks = (params) => apiClient.get('/api/tasks', { params });
export const getTaskFailureStats = (params) => apiClient.get('/api/tasks/failure-stats', { params });
export const retryTask = (taskId) => apiClient.post(`/api/tasks/${taskId}/retry`);
export const cancelTask = (taskId) => apiClient.post(`/api/tasks/${taskId}/cancel`);
