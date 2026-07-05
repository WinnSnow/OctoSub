import apiClient from './client';

export const getDashboardSummary = () => apiClient.get('/api/dashboard/summary');
