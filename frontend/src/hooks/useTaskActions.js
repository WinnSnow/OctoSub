import { useState } from 'react';
import toast from 'react-hot-toast';

import { cancelTask, retryTask } from '../api/tasks';
import { retryDownloadHistoryTransfer } from '../api/subscriptions';
import { getApiErrorMessage } from '../api/errors';

export function useTaskActions({ fetchTasks }) {
  const [retryingTaskId, setRetryingTaskId] = useState('');
  const [stoppingTaskId, setStoppingTaskId] = useState('');

  const handleRetryTask = async (task) => {
    setRetryingTaskId(task.task_id);
    try {
      const response = task.type === 'transfer' && task.history_id
        ? await retryDownloadHistoryTransfer(task.history_id)
        : await retryTask(task.task_id);
      toast.success(response.data?.message || '重试任务已启动');
      await fetchTasks();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '重试任务失败'));
    } finally {
      setRetryingTaskId('');
    }
  };

  const handleCancelTask = async (task) => {
    setStoppingTaskId(task.task_id);
    try {
      await cancelTask(task.task_id);
      toast.success('已请求停止任务');
      await fetchTasks();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '停止任务失败'));
    } finally {
      setStoppingTaskId('');
    }
  };

  return {
    retryingTaskId,
    stoppingTaskId,
    handleRetryTask,
    handleCancelTask,
  };
}
