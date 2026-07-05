import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { getSubscriptionScheduler, getSubscriptions } from '../api/subscriptions';

export function useSubscriptionsData() {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [scheduler, setScheduler] = useState(null);

  const refreshSubscriptions = useCallback(async () => {
    setLoading(true);
    try {
      const [response, schedulerResponse] = await Promise.all([
        getSubscriptions(),
        getSubscriptionScheduler().catch(() => ({ data: null })),
      ]);
      setSubscriptions(response.data);
      setScheduler(schedulerResponse.data);
    } catch (error) {
      toast.error('获取订阅列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSubscriptions();
  }, [refreshSubscriptions]);

  return {
    subscriptions,
    loading,
    scheduler,
    refreshSubscriptions,
  };
}
