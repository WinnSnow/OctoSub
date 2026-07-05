import React from 'react';
import { Square } from 'lucide-react';

const STATUS_LABELS = {
  queued: '排队中',
  running: '运行中',
  cancel_requested: '停止中',
  cancelled: '已停止',
  completed: '已完成',
  failed: '失败',
  partial_failed: '部分失败',
};

const CANCELLABLE_TASK_TYPES = new Set(['fetch', 'poster_match', 'subscription_check', 'subscription_refresh']);

function TaskProgressStrip({ task, onCancel, cancelling = false }) {
  if (!task) return null;
  const progressText = `${task.current || 0}${task.total ? ` / ${task.total}` : ''}`;
  const canCancel = Boolean(onCancel)
    && CANCELLABLE_TASK_TYPES.has(task.type)
    && ['queued', 'running', 'cancel_requested'].includes(task.status);
  const cancelDisabled = cancelling || task.status === 'cancel_requested';
  return (
    <section className="task-strip">
      <div className="d-flex justify-content-between gap-3 align-items-center mb-2">
        <strong>{STATUS_LABELS[task.status] || task.status}</strong>
        <div className="d-inline-flex align-items-center gap-2">
          <span className="text-muted small">{progressText}</span>
          {canCancel && (
            <button
              type="button"
              className="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1"
              onClick={onCancel}
              disabled={cancelDisabled}
            >
              <Square size={13} />
              {cancelDisabled ? '停止中' : '停止'}
            </button>
          )}
        </div>
      </div>
      <div className="progress mb-2" style={{ height: 8 }}>
        <div className="progress-bar progress-bar-striped progress-bar-animated" style={{ width: task.total ? `${Math.min(100, (task.current / task.total) * 100)}%` : '100%' }} />
      </div>
      <div className="text-muted small text-truncate">{task.message}</div>
    </section>
  );
}

export default TaskProgressStrip;
