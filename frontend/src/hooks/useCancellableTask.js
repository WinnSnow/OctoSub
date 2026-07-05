import { useState } from 'react';
import toast from 'react-hot-toast';

import { cancelTask } from '../api/tasks';
import { getApiErrorMessage } from '../api/errors';
import { isCancellableTaskStatus } from '../utils/taskStatus';

export function useCancellableTask({
  task,
  onCancelled,
  successMessage = '已请求停止任务',
  errorMessage = '停止任务失败',
} = {}) {
  const [cancellingTaskId, setCancellingTaskId] = useState('');

  const cancelCurrentTask = async () => {
    if (!task?.task_id || !isCancellableTaskStatus(task.status)) return;
    setCancellingTaskId(task.task_id);
    try {
      const response = await cancelTask(task.task_id);
      const nextTask = response.data?.task || response.data || {};
      onCancelled?.({
        ...nextTask,
        status: nextTask.status || 'cancel_requested',
        message: nextTask.message || '正在停止任务...',
      });
      toast.success(successMessage);
    } catch (error) {
      toast.error(getApiErrorMessage(error, errorMessage));
      setCancellingTaskId('');
    }
  };

  return {
    cancellingTaskId,
    setCancellingTaskId,
    cancelCurrentTask,
  };
}
