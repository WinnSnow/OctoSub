import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { getDownloadHistory, getSubscriptions } from '../api/subscriptions';

const DEFAULT_HISTORY_STATS = { total: 0, submitted: 0, success: 0, failed: 0, skipped: 0 };

function statsFromItems(items) {
  return {
    total: items.length,
    submitted: items.filter(item => item.status === 'submitted').length,
    success: items.filter(item => item.status === 'success').length,
    failed: items.filter(item => item.status === 'failed').length,
    skipped: items.filter(item => item.status === 'skipped').length,
  };
}

export function useDownloadHistoryData({
  page,
  pageSize,
  selectedSubscription,
  statusFilter,
  setPage,
}) {
  const [history, setHistory] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState(DEFAULT_HISTORY_STATS);

  const fetchSubscriptions = useCallback(async () => {
    try {
      const response = await getSubscriptions();
      setSubscriptions(response.data);
    } catch (error) {
      console.error('获取订阅列表失败', error);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit: pageSize };
      if (selectedSubscription) {
        params.subscription_id = selectedSubscription;
      }
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }

      const response = await getDownloadHistory(params);
      const payload = response.data || {};
      if (Array.isArray(payload)) {
        setHistory(payload);
        setTotal(payload.length);
        setStats(statsFromItems(payload));
      } else {
        setHistory(payload.items || []);
        setTotal(payload.total || 0);
        setStats(payload.stats || { ...DEFAULT_HISTORY_STATS, total: payload.total || 0 });
      }
    } catch (error) {
      toast.error('获取下载历史失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedSubscription, statusFilter]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const resetToFirstPage = useCallback(() => {
    setPage(1);
  }, [setPage]);

  return {
    history,
    subscriptions,
    loading,
    total,
    stats,
    fetchHistory,
    resetToFirstPage,
  };
}
