import { useEffect, useRef } from 'react';

import { getTask } from '../api/tasks';
import { isActiveTaskStatus, isFinalTaskStatus } from '../utils/taskStatus';

function useLatestRef(value) {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref;
}

export function useTaskPolling({
  task,
  pollInterval = 2000,
  onProgress,
  onCompleted,
  onFailed,
  onCancelled,
  onMissing,
}) {
  const taskRef = useLatestRef(task);
  const callbacksRef = useLatestRef({
    onProgress,
    onCompleted,
    onFailed,
    onCancelled,
    onMissing,
  });
  const taskId = task?.task_id;
  const taskStatus = task?.status;

  useEffect(() => {
    if (!taskId || !isActiveTaskStatus(taskStatus)) return undefined;

    let inFlight = false;
    const intervalId = setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await getTask(taskId);
        const data = response.data;
        callbacksRef.current.onProgress?.(data);

        if (!isFinalTaskStatus(data.status)) return;

        clearInterval(intervalId);
        if (data.status === 'completed') {
          callbacksRef.current.onCompleted?.(data);
        } else if (data.status === 'cancelled') {
          callbacksRef.current.onCancelled?.(data);
        } else {
          callbacksRef.current.onFailed?.(data);
        }
      } catch (error) {
        if (error.response?.status === 404) {
          clearInterval(intervalId);
          callbacksRef.current.onMissing?.(taskRef.current);
        }
      } finally {
        inFlight = false;
      }
    }, pollInterval);

    return () => clearInterval(intervalId);
  }, [callbacksRef, pollInterval, taskId, taskRef, taskStatus]);
}
