import apiClient from './client';

export const getSubscriptions = () => apiClient.get('/api/subscriptions');
export const createSubscription = (payload) => apiClient.post('/api/subscriptions', payload);
export const updateSubscription = (id, payload) => apiClient.put(`/api/subscriptions/${id}`, payload);
export const updateSubscriptionStatus = (id, payload) => apiClient.patch(`/api/subscriptions/${id}/status`, payload);
export const deleteSubscription = (id) => apiClient.delete(`/api/subscriptions/${id}`);
export const checkSubscriptions = (subscriptionId = null) => apiClient.post('/api/subscriptions/check', subscriptionId ? { subscription_id: subscriptionId } : {});
export const refreshSubscriptionLifecycle = (subscriptionId = null) => apiClient.post('/api/subscriptions/refresh-lifecycle', subscriptionId ? { subscription_id: subscriptionId } : {});
export const getSubscriptionScheduler = () => apiClient.get('/api/subscriptions/scheduler');
export const getDownloadHistory = (params) => apiClient.get('/api/download-history', { params });
export const syncDownloadHistoryFromCms = () => apiClient.post('/api/download-history/sync-cms');
export const retryDownloadHistoryTransfer = (historyId) => apiClient.post(`/api/download-history/${historyId}/retry`);
