import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';

import { getApiErrorMessage } from '../api/errors';
import { checkSubscriptions, refreshSubscriptionLifecycle } from '../api/subscriptions';
import { useCancellableTask } from './useCancellableTask';
import { useTaskPolling } from './useTaskPolling';

export function useSubscriptionTaskController({ refreshSubscriptions }) {
  const [checking, setChecking] = useState(false);
  const [checkingId, setCheckingId] = useState(null);
  const [activeTask, setActiveTask] = useState(null);
  const clearTaskTimerRef = useRef(null);

  const clearTaskTimer = useCallback(() => {
    if (clearTaskTimerRef.current) {
      clearTimeout(clearTaskTimerRef.current);
      clearTaskTimerRef.current = null;
    }
  }, []);

  const startActiveTask = useCallback((task) => {
    clearTaskTimer();
    setActiveTask(task);
  }, [clearTaskTimer]);

  const clearTaskFlags = useCallback(() => {
    setChecking(false);
    setCheckingId(null);
  }, []);

  const { cancellingTaskId, setCancellingTaskId, cancelCurrentTask } = useCancellableTask({
    task: activeTask,
    successMessage: '正在停止订阅任务',
    errorMessage: '停止任务失败',
    onCancelled: nextTask => setActiveTask(prev => ({ ...prev, ...nextTask })),
  });

  const clearFinishedTask = useCallback((taskId) => {
    clearTaskFlags();
    setCancellingTaskId('');
    clearTaskTimer();
    clearTaskTimerRef.current = setTimeout(() => {
      setActiveTask(prev => (prev?.task_id === taskId ? null : prev));
      clearTaskTimerRef.current = null;
    }, 5000);
  }, [clearTaskFlags, clearTaskTimer, setCancellingTaskId]);

  useEffect(() => clearTaskTimer, [clearTaskTimer]);

  useTaskPolling({
    task: activeTask,
    pollInterval: 2000,
    onProgress: data => setActiveTask(prev => ({ ...prev, ...data })),
    onCompleted: async (data) => {
      toast.success(data.message || '任务已完成');
      await refreshSubscriptions();
      clearFinishedTask(data.task_id || activeTask?.task_id);
    },
    onCancelled: async (data) => {
      toast.success(data.message || '任务已停止');
      await refreshSubscriptions();
      clearFinishedTask(data.task_id || activeTask?.task_id);
    },
    onFailed: (data) => {
      toast.error(data.message || '任务失败');
      clearFinishedTask(data.task_id || activeTask?.task_id);
    },
    onMissing: () => {
      setActiveTask(null);
      clearTaskFlags();
      setCancellingTaskId('');
    },
  });

  const handleManualCheck = async () => {
    if (!window.confirm('确定检查订阅下一集吗？此操作会搜索每个订阅的下一个追更目标。')) return;

    setChecking(true);
    let startedTask = false;
    try {
      const response = await checkSubscriptions();
      if (response.data?.task_id) {
        startedTask = true;
        startActiveTask({
          task_id: response.data.task_id,
          type: 'subscription_check',
          title: '检查订阅下一集',
          total: 0,
          current: 0,
          status: response.data.status || 'running',
          message: response.data.message || '订阅检查任务已启动',
        });
      }
      toast.success(response.data?.message || '订阅检查任务已启动');
    } catch (error) {
      toast.error('启动失败');
      setChecking(false);
    } finally {
      if (!startedTask) {
        setChecking(false);
      }
    }
  };

  const startLifecycleRefresh = useCallback(async (subscriptionId = null, title = '同步订阅状态') => {
    setChecking(true);
    let startedTask = false;
    try {
      const response = await refreshSubscriptionLifecycle(subscriptionId);
      if (response.data?.task_id) {
        startedTask = true;
        startActiveTask({
          task_id: response.data.task_id,
          type: 'subscription_refresh',
          title,
          total: 0,
          current: 0,
          status: response.data.status || 'running',
          message: response.data.message || '订阅状态同步任务已启动',
        });
      }
      toast.success(response.data?.message || '订阅状态同步任务已启动');
    } catch (error) {
      toast.error(getApiErrorMessage(error, '同步状态失败'));
      setChecking(false);
    } finally {
      if (!startedTask) {
        setChecking(false);
      }
    }
  }, []);

  const handleRefreshLifecycle = async () => {
    await startLifecycleRefresh(null, '同步订阅状态');
  };

  const handleSingleCheck = async (sub) => {
    setCheckingId(sub.id);
    let startedTask = false;
    try {
      const response = await checkSubscriptions(sub.id);
      if (response.data?.task_id) {
        startedTask = true;
        startActiveTask({
          task_id: response.data.task_id,
          type: 'subscription_check',
          title: `检查下一集：${sub.keyword}`,
          total: 0,
          current: 0,
          status: response.data.status || 'running',
          message: response.data.message || `已启动下一集检查：${sub.keyword}`,
        });
      }
      toast.success(response.data?.message || `已启动下一集检查：${sub.keyword}`);
    } catch (error) {
      toast.error('启动失败');
      setCheckingId(null);
    } finally {
      if (!startedTask) {
        setCheckingId(null);
      }
    }
  };

  return {
    checking,
    checkingId,
    activeTask,
    cancellingTaskId,
    handleManualCheck,
    handleRefreshLifecycle,
    handleSingleCheck,
    handleCancelTask: cancelCurrentTask,
    startLifecycleRefresh,
  };
}
