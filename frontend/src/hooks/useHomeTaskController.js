import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';

import { getApiErrorMessage } from '../api/errors';
import { cancelTask, getTask, getTasks } from '../api/tasks';
import {
  HOME_TASK_CLEAR_DELAY_MS,
  HOME_TASK_POLL_INTERVAL_MS,
} from '../config/app';
import { ACTIVE_TASK_STATUSES, FINAL_TASK_STATUSES } from '../utils/taskStatus';

const HOME_ACTIVE_TASK_KEY = 'tg-web-view:home-active-task-id';
const STALE_PREPARING_TASK_SECONDS = 300;

function isStalePreparingTask(task) {
  if (!task || !ACTIVE_TASK_STATUSES.has(task.status)) return false;
  if (task.type !== 'poster_match') return false;
  if ((task.current || 0) !== 0 || (task.total || 0) !== 0) return false;
  if (!String(task.message || '').includes('准备中')) return false;
  const updatedAt = Number(task.updated_at || task.created_at || 0);
  if (!updatedAt) return false;
  return (Date.now() / 1000) - updatedAt > STALE_PREPARING_TASK_SECONDS;
}

export function useHomeTaskController({
  mode,
  page,
  runSearch,
  fetchPosterWall,
  startPosterRefresh,
}) {
  const [scraping, setScraping] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [cancellingTaskId, setCancellingTaskId] = useState('');
  const handledFinalTaskIdsRef = useRef(new Set());
  const clearTaskTimerRef = useRef(null);

  const clearTaskTimer = useCallback(() => {
    if (clearTaskTimerRef.current) {
      clearTimeout(clearTaskTimerRef.current);
      clearTaskTimerRef.current = null;
    }
  }, []);

  const saveHomeTaskId = useCallback((taskId) => {
    if (!taskId) return;
    window.localStorage.setItem(HOME_ACTIVE_TASK_KEY, taskId);
  }, []);

  const clearHomeTaskId = useCallback((taskId = null) => {
    const savedTaskId = window.localStorage.getItem(HOME_ACTIVE_TASK_KEY);
    if (!taskId || savedTaskId === taskId) {
      window.localStorage.removeItem(HOME_ACTIVE_TASK_KEY);
    }
  }, []);

  const trackTask = useCallback((task) => {
    if (!task?.task_id) return;
    clearTaskTimer();
    handledFinalTaskIdsRef.current.delete(task.task_id);
    setActiveTask(task);
    saveHomeTaskId(task.task_id);
  }, [clearTaskTimer, saveHomeTaskId]);

  const clearFinishedTask = useCallback((taskId) => {
    clearTaskTimer();
    clearTaskTimerRef.current = setTimeout(() => {
      setActiveTask(prev => (prev?.task_id === taskId ? null : prev));
      clearTaskTimerRef.current = null;
    }, HOME_TASK_CLEAR_DELAY_MS);
  }, [clearTaskTimer]);

  const applyRestoredTask = useCallback((task) => {
    if (!task?.task_id || !ACTIVE_TASK_STATUSES.has(task.status)) return false;
    if (isStalePreparingTask(task)) return false;
    trackTask(task);
    return true;
  }, [trackTask]);

  const restoreHomeTask = useCallback(async () => {
    const savedTaskId = window.localStorage.getItem(HOME_ACTIVE_TASK_KEY);
    if (savedTaskId) {
      try {
        const response = await getTask(savedTaskId);
        if (applyRestoredTask(response.data)) return;
      } catch {
        // Fall through to task-list recovery.
      }
      clearHomeTaskId(savedTaskId);
    }

    for (const status of ['queued', 'running', 'cancel_requested']) {
      try {
        const response = await getTasks({ status, task_type: 'fetch', page: 1, limit: 1 });
        const task = response.data?.items?.[0];
        if (applyRestoredTask(task)) return;
      } catch {
        // Recovery is opportunistic; normal search remains available.
      }
    }
  }, [applyRestoredTask, clearHomeTaskId]);

  useEffect(() => {
    restoreHomeTask();
  }, [restoreHomeTask]);

  useEffect(() => clearTaskTimer, [clearTaskTimer]);

  useEffect(() => {
    if (!activeTask || !ACTIVE_TASK_STATUSES.has(activeTask.status)) return undefined;
    const intervalId = setInterval(async () => {
      try {
        const response = await getTask(activeTask.task_id);
        const data = response.data;
        setActiveTask(prev => ({ ...prev, ...data }));
        if (FINAL_TASK_STATUSES.has(data.status)) {
          clearInterval(intervalId);
          const finalTaskId = data.task_id || activeTask.task_id;
          if (handledFinalTaskIdsRef.current.has(finalTaskId)) {
            return;
          }
          handledFinalTaskIdsRef.current.add(finalTaskId);
          const taskType = data.type || activeTask.type;
          const posterBackfillTaskId = data.result?.poster_backfill_task_id;
          if (data.status === 'completed' && taskType === 'fetch' && posterBackfillTaskId) {
            try {
              const posterTaskResponse = await getTask(posterBackfillTaskId);
              if (ACTIVE_TASK_STATUSES.has(posterTaskResponse.data?.status)) {
                handledFinalTaskIdsRef.current.delete(posterBackfillTaskId);
                setActiveTask(posterTaskResponse.data);
                saveHomeTaskId(posterBackfillTaskId);
                toast.success(data.message || '抓取完成，正在自动补海报');
                return;
              }
              if (FINAL_TASK_STATUSES.has(posterTaskResponse.data?.status)) {
                handledFinalTaskIdsRef.current.add(posterBackfillTaskId);
                setActiveTask(posterTaskResponse.data);
                toast.success(posterTaskResponse.data.message || data.message || '抓取和自动补海报已完成');
                if (mode === 'local') {
                  runSearch({ forceRefresh: true, nextPage: page });
                }
                fetchPosterWall().catch(() => {});
                startPosterRefresh();
                clearHomeTaskId(finalTaskId);
                clearHomeTaskId(posterBackfillTaskId);
                clearFinishedTask(posterTaskResponse.data.task_id || posterBackfillTaskId);
                return;
              }
            } catch {
              // If the poster task is already gone, finish the fetch task normally.
            }
          }
          if (['completed', 'cancelled'].includes(data.status)) {
            toast.success(data.status === 'cancelled' ? '已停止，已保留已匹配海报' : (data.message || '任务完成'));
            if (mode === 'local') {
              runSearch({ forceRefresh: true, nextPage: page });
            }
            if (taskType === 'poster_match' || (data.message || '').includes('补海报')) {
              fetchPosterWall().catch(() => {});
              startPosterRefresh();
            }
          } else {
            toast.error(data.message || '任务失败');
          }
          clearHomeTaskId(finalTaskId);
          clearFinishedTask(finalTaskId);
        }
      } catch (error) {
        if (error.response?.status === 404) {
          clearInterval(intervalId);
          clearHomeTaskId(activeTask.task_id);
          setActiveTask(null);
        }
      }
    }, HOME_TASK_POLL_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [activeTask, clearFinishedTask, clearHomeTaskId, fetchPosterWall, mode, page, runSearch, saveHomeTaskId, startPosterRefresh]);

  const cancelActiveTask = async () => {
    if (!activeTask || !['queued', 'running'].includes(activeTask.status)) return;
    setCancellingTaskId(activeTask.task_id);
    try {
      const response = await cancelTask(activeTask.task_id);
      const nextTask = response.data?.task || response.data;
      setActiveTask(prev => ({
        ...prev,
        ...nextTask,
        status: nextTask?.status || 'cancel_requested',
        message: nextTask?.message || '正在停止任务...',
      }));
      toast.success('已请求停止任务');
    } catch (error) {
      toast.error(getApiErrorMessage(error, '停止任务失败'));
    } finally {
      setCancellingTaskId('');
    }
  };

  const startTask = async (request, taskDefaults = {}) => {
    setScraping(true);
    try {
      const response = await request();
      const { task_id, message, count } = response.data;
      if (task_id) {
        trackTask({
          task_id,
          ...taskDefaults,
          channel: response.data.channel || '任务',
          total: count || 0,
          current: 0,
          status: response.data.status || 'running',
          message: message || '任务已启动',
        });
      }
      toast.success(message || '任务已启动');
    } catch (error) {
      toast.error(getApiErrorMessage(error, '启动任务失败'));
    } finally {
      setScraping(false);
    }
  };

  return {
    activeTask,
    scraping,
    cancellingTaskId,
    setActiveTask,
    trackTask,
    startTask,
    cancelActiveTask,
  };
}
