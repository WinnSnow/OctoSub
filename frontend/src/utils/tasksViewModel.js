import { ACTIVE_TASK_STATUSES, isCancellableTaskStatus } from './taskStatus';

export const TASK_STATUS_FILTERS = [
  ['all', '全部'],
  ['queued', '排队中'],
  ['running', '运行中'],
  ['cancel_requested', '停止中'],
  ['cancelled', '已停止'],
  ['completed', '已完成'],
  ['failed', '失败'],
];

export const TASK_TYPE_LABELS = {
  fetch: '频道抓取',
  retry: '补链重试',
  retry_missing_links: '补链重试',
  poster_match: '海报匹配',
  transfer: '资源转存',
  cms_sync: 'CMS 同步',
  subscription_check: '订阅检查',
  subscription_refresh: '状态刷新',
  jellyfin_library_sync: 'Jellyfin 同步',
};

const RETRYABLE_TASK_TYPES = new Set(['subscription_check', 'subscription_refresh', 'cms_sync', 'poster_match']);
const KNOWN_TASK_TYPES = new Set(Object.keys(TASK_TYPE_LABELS));
const CANCELLABLE_TASK_TYPES = new Set([
  'fetch',
  'retry',
  'retry_missing_links',
  'poster_match',
  'subscription_check',
  'subscription_refresh',
  'jellyfin_library_sync',
]);
const TASK_CORE_FIELDS = new Set([
  'task_id',
  'type',
  'title',
  'total',
  'current',
  'status',
  'message',
  'result',
  'error',
  'created_at',
  'updated_at',
  'finished_at',
]);

export function getTaskTypeLabel(type) {
  return TASK_TYPE_LABELS[type] || type || '任务';
}

export function isKnownTask(task) {
  return KNOWN_TASK_TYPES.has(task?.type);
}

export function formatProgress(task) {
  if (!task.total) {
    if (task.status === 'queued') return '排队中';
    if (task.status === 'running') return '进行中';
    return '-';
  }
  return `${task.current || 0}/${task.total}`;
}

export function getTaskMetadata(task) {
  return Object.fromEntries(
    Object.entries(task).filter(([key, value]) => !TASK_CORE_FIELDS.has(key) && value !== undefined && value !== null && value !== ''),
  );
}

export function canRetryTask(task) {
  if (task.status !== 'failed') return false;
  if (RETRYABLE_TASK_TYPES.has(task.type)) return true;
  return task.type === 'transfer' && Boolean(task.history_id);
}

export function canCancelTask(task) {
  return isCancellableTaskStatus(task.status) && CANCELLABLE_TASK_TYPES.has(task.type);
}

export function hasActiveTask(tasks) {
  return tasks.some(task => ACTIVE_TASK_STATUSES.has(task.status));
}

export function buildTaskStats(tasks, total) {
  return {
    total,
    running: tasks.filter(task => ACTIVE_TASK_STATUSES.has(task.status)).length,
    completed: tasks.filter(task => task.status === 'completed').length,
    failed: tasks.filter(task => task.status === 'failed').length,
  };
}

export function getFocusedTaskIdFromLocation() {
  if (typeof window === 'undefined') return '';
  return new URLSearchParams(window.location.search).get('task_id') || '';
}
