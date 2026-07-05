import apiClient from './client';

export const transferResource = (payload) => apiClient.post('/api/transfer', payload);
export const getPendingTransfers = (params) => apiClient.get('/api/pending-transfers', { params });
export const resolvePendingTransfer = (id, action) => apiClient.post(`/api/pending-transfers/${id}/${action}`);
export const confirmPendingTransferLibrary = (id) => apiClient.post(`/api/pending-transfers/${id}/confirm-library`);
