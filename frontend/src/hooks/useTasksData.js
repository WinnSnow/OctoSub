import { useCallback, useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';

import { getTask, getTaskFailureStats, getTasks } from '../api/tasks';
import { getApiErrorMessage } from '../api/errors';
import {
  buildTaskStats,
  getFocusedTaskIdFromLocation,
  hasActiveTask,
  isKnownTask,
} from '../utils/tasksViewModel';

export function useTasksData({ page, pageSize, statusFilter }) {
  const [tasks, setTasks] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [expandedTaskIds, setExpandedTaskIds] = useState(() => new Set());
  const [failureStats, setFailureStats] = useState([]);
  const [focusedTaskId] = useState(getFocusedTaskIdFromLocation);

  const fetchTasks = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const params = { page, limit: pageSize };
      if (statusFilter !== 'all') params.status = statusFilter;
      const [response, failureResponse] = await Promise.all([
        getTasks(params),
        getTaskFailureStats({ limit: 5 }).catch(() => ({ data: { items: [] } })),
      ]);
      const payload = response.data || {};
      let nextTasks = (payload.items || []).filter(isKnownTask);
      if (focusedTaskId && !nextTasks.some(task => task.task_id === focusedTaskId)) {
        try {
          const focusedResponse = await getTask(focusedTaskId);
          const focusedTask = focusedResponse.data;
          if (focusedTask?.task_id && isKnownTask(focusedTask)) {
            nextTasks = [focusedTask, ...nextTasks];
          }
        } catch {
          // The task may have been pruned; keep the normal task list visible.
        }
      }
      setTasks(nextTasks);
      setTotal(payload.total ?? nextTasks.length);
      setFailureStats(failureResponse.data?.items || []);
      if (focusedTaskId && nextTasks.some(task => task.task_id === focusedTaskId)) {
        setExpandedTaskIds(prev => new Set(prev).add(focusedTaskId));
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, '获取任务列表失败'));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [focusedTaskId, page, pageSize, statusFilter]);

  const toggleTaskDetails = useCallback((taskId) => {
    setExpandedTaskIds(prev => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    if (!hasActiveTask(tasks)) return undefined;
    const timer = window.setInterval(() => {
      fetchTasks({ silent: true });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [fetchTasks, tasks]);

  const stats = useMemo(() => buildTaskStats(tasks, total), [tasks, total]);

  return {
    tasks,
    total,
    loading,
    expandedTaskIds,
    failureStats,
    focusedTaskId,
    stats,
    fetchTasks,
    toggleTaskDetails,
  };
}
