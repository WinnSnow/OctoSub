import { useState } from 'react';
import toast from 'react-hot-toast';

import { retryDownloadHistoryTransfer, syncDownloadHistoryFromCms } from '../api/subscriptions';
import { useTaskPolling } from './useTaskPolling';
import { summarizeTransferFailure } from '../utils/transferStatus';

export function useDownloadHistoryTasks({
  fetchHistory,
  resetToFirstPage,
}) {
  const [syncing, setSyncing] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [retryingHistoryId, setRetryingHistoryId] = useState(null);

  const finishTaskAndRefresh = async () => {
    resetToFirstPage();
    await fetchHistory();
    setActiveTask(null);
    setSyncing(false);
  };

  const handleSyncCms = async () => {
    setSyncing(true);
    let startedTask = false;
    try {
      const response = await syncDownloadHistoryFromCms();
      if (response.data?.task_id) {
        startedTask = true;
        setActiveTask({
          task_id: response.data.task_id,
          type: 'cms_sync',
          title: 'CMS 转存同步',
          total: 0,
          current: 0,
          status: response.data.status || 'running',
          message: response.data.message || 'CMS 同步任务已启动',
        });
        toast.success(response.data.message || 'CMS 同步任务已启动');
      } else {
        toast.success(`CMS 同步完成，更新 ${response.data?.updated || 0} 条`);
        await finishTaskAndRefresh();
      }
    } catch (error) {
      toast.error('CMS 转存结果同步失败');
    } finally {
      if (!startedTask) {
        setSyncing(false);
      }
    }
  };

  const handleRetryTransfer = async (item) => {
    setRetryingHistoryId(item.id);
    try {
      const response = await retryDownloadHistoryTransfer(item.id);
      if (response.data?.task_id) {
        setActiveTask({
          task_id: response.data.task_id,
          type: 'transfer',
          title: `转存重试：${item.title || item.fingerprint}`,
          total: 0,
          current: 0,
          status: 'running',
          message: response.data.message || '转存重试任务已启动',
        });
      }
      toast.success(response.data?.message || '转存重试任务已启动');
      await fetchHistory();
    } catch (error) {
      toast.error('转存重试失败');
    } finally {
      setRetryingHistoryId(null);
    }
  };

  useTaskPolling({
    task: activeTask,
    pollInterval: 2000,
    onProgress: data => setActiveTask(prev => ({ ...prev, ...data })),
    onCompleted: async (data) => {
      toast.success(data.message || 'CMS 同步完成');
      await finishTaskAndRefresh();
    },
    onFailed: (data) => {
      const summary = data.type === 'transfer'
        ? summarizeTransferFailure(data.error || data.message)
        : (data.message || 'CMS 同步失败');
      toast.error(summary);
      setActiveTask(null);
      setSyncing(false);
    },
    onCancelled: async (data) => {
      toast.success(data.message || '任务已停止');
      await finishTaskAndRefresh();
    },
    onMissing: () => {
      setActiveTask(null);
      setSyncing(false);
    },
  });

  return {
    syncing,
    activeTask,
    retryingHistoryId,
    handleSyncCms,
    handleRetryTransfer,
  };
}
