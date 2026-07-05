export const ACTIVE_TASK_STATUSES = new Set(['queued', 'running', 'cancel_requested']);
export const CANCELLABLE_TASK_STATUSES = new Set(['queued', 'running']);
export const FINAL_TASK_STATUSES = new Set(['completed', 'cancelled', 'failed', 'partial_failed']);

export function isActiveTaskStatus(status) {
  return ACTIVE_TASK_STATUSES.has(status);
}

export function isCancellableTaskStatus(status) {
  return CANCELLABLE_TASK_STATUSES.has(status);
}

export function isFinalTaskStatus(status) {
  return FINAL_TASK_STATUSES.has(status);
}
