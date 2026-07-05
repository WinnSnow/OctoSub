import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, ListChecks, Loader2, RefreshCcw, Square } from 'lucide-react';

import { EmptyState, IconButton, LoadingState, PageHeader, Panel, StatTile, StatusBadge } from '../components/ui';
import { useTaskActions } from '../hooks/useTaskActions';
import { useTasksData } from '../hooks/useTasksData';
import { useIsNarrowViewport } from '../hooks/useViewport';
import { formatDateTime } from '../utils/text';
import {
  TASK_STATUS_FILTERS,
  canCancelTask,
  canRetryTask,
  formatProgress,
  getTaskMetadata,
  getTaskTypeLabel,
} from '../utils/tasksViewModel';

function JsonSummary({ value }) {
  if (!value || Object.keys(value).length === 0) return null;
  return (
    <code className="task-json-summary">
      {JSON.stringify(value)}
    </code>
  );
}

function JsonBlock({ label, value }) {
  if (value === undefined || value === null || (typeof value === 'object' && Object.keys(value).length === 0)) return null;
  return (
    <div className="task-detail-block">
      <div className="task-detail-label">{label}</div>
      <pre>{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function TaskActionButtons({
  task,
  expanded,
  retryingTaskId,
  stoppingTaskId,
  onToggleDetails,
  onRetryTask,
  onCancelTask,
}) {
  return (
    <div className="task-actions">
      <button className="btn btn-outline-secondary btn-sm" onClick={() => onToggleDetails(task.task_id)}>
        {expanded ? '收起' : '详情'}
      </button>
      {canRetryTask(task) && (
        <button
          className="btn btn-outline-secondary btn-sm"
          onClick={() => onRetryTask(task)}
          disabled={retryingTaskId === task.task_id}
        >
          {retryingTaskId === task.task_id ? '重试中...' : '重试'}
        </button>
      )}
      {canCancelTask(task) && (
        <button
          className="btn btn-outline-danger btn-sm"
          onClick={() => onCancelTask(task)}
          disabled={stoppingTaskId === task.task_id}
        >
          <Square size={13} />
          {stoppingTaskId === task.task_id ? '停止中...' : '停止'}
        </button>
      )}
    </div>
  );
}

function TasksPage() {
  const isMobile = useIsNarrowViewport();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('all');
  const pageSize = 50;
  const {
    tasks,
    total,
    loading,
    expandedTaskIds,
    failureStats,
    focusedTaskId,
    stats,
    fetchTasks,
    toggleTaskDetails,
  } = useTasksData({ page, pageSize, statusFilter });
  const {
    retryingTaskId,
    stoppingTaskId,
    handleRetryTask,
    handleCancelTask,
  } = useTaskActions({ fetchTasks });

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Task Center"
        title="任务中心"
        description="集中查看抓取、订阅检查、转存、CMS 同步等后台任务的状态和结果。"
        actions={(
          <IconButton icon={RefreshCcw} className="btn-outline-primary" onClick={fetchTasks} disabled={loading}>
            刷新
          </IconButton>
        )}
      />

      <div className="stat-grid mb-3">
        <StatTile label="任务总数" value={stats.total} icon={ListChecks} tone="primary" />
        <StatTile label="活跃任务" value={stats.running} icon={Loader2} tone="warning" />
        <StatTile label="已完成" value={stats.completed} icon={CheckCircle2} tone="success" />
        <StatTile label="失败" value={stats.failed} icon={AlertTriangle} tone="danger" />
      </div>

      {failureStats.length > 0 && (
        <Panel className="mb-3" compact>
          <div className="system-section-title">
            <span>失败原因统计</span>
            <small className="text-muted">按任务类型和错误原因聚合</small>
          </div>
          {isMobile ? (
            <div className="mobile-record-list task-failure-mobile-list">
              {failureStats.map(item => (
                <article className="mobile-record-card task-failure-mobile-card" key={`${item.type}-${item.reason}`}>
                  <div className="mobile-record-head">
                    <div className="min-w-0">
                      <div className="mobile-record-title">{getTaskTypeLabel(item.type)}</div>
                      <div className="small text-muted">
                        最近出现：{item.latest_updated_at ? formatDateTime(item.latest_updated_at * 1000) : '-'}
                      </div>
                    </div>
                    <StatusBadge status="failed">{item.count} 次</StatusBadge>
                  </div>
                  <div className="mobile-record-section task-failure-reason">
                    <div className="mobile-record-label">原因</div>
                    {item.reason || '-'}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="table-responsive">
              <table className="table table-hover mb-0">
                <thead className="table-light">
                  <tr>
                    <th style={{ width: '140px' }}>类型</th>
                    <th>原因</th>
                    <th style={{ width: '90px' }}>次数</th>
                    <th style={{ width: '170px' }}>最近出现</th>
                  </tr>
                </thead>
                <tbody>
                  {failureStats.map(item => (
                    <tr key={`${item.type}-${item.reason}`}>
                      <td>{getTaskTypeLabel(item.type)}</td>
                      <td className="text-break">{item.reason}</td>
                      <td className="fw-semibold">{item.count}</td>
                      <td className="small text-muted">{item.latest_updated_at ? formatDateTime(item.latest_updated_at * 1000) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      <div className="segmented-control compact mb-3">
        {TASK_STATUS_FILTERS.map(([value, label]) => (
          <button
            key={value}
            className={statusFilter === value ? 'active' : ''}
            onClick={() => {
              setStatusFilter(value);
              setPage(1);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <LoadingState label="正在加载任务..." />}

      {!loading && tasks.length === 0 && (
        <EmptyState icon={Clock3} title="暂无任务" description="启动抓取、订阅检查或转存后，任务会出现在这里。" />
      )}

      {!loading && tasks.length > 0 && (
        <Panel compact>
          {isMobile ? (
            <div className="mobile-record-list task-mobile-list">
              {tasks.map(task => {
                const expanded = expandedTaskIds.has(task.task_id);
                const metadata = getTaskMetadata(task);
                return (
                  <article className={`mobile-record-card task-mobile-card ${task.task_id === focusedTaskId ? 'task-focused-card' : ''}`} key={task.task_id}>
                    <div className="mobile-record-head">
                      <div className="min-w-0">
                        <div className="mobile-record-title">{task.title || getTaskTypeLabel(task.type)}</div>
                        <div className="small text-muted text-break">{task.task_id}</div>
                      </div>
                      <StatusBadge status={task.status} />
                    </div>
                    <div className="mobile-record-grid">
                      <div>
                        <span>类型</span>
                        <strong>{getTaskTypeLabel(task.type)}</strong>
                      </div>
                      <div>
                        <span>进度</span>
                        <strong>{formatProgress(task)}</strong>
                      </div>
                      <div>
                        <span>更新时间</span>
                        <strong>{formatDateTime(task.updated_at ? task.updated_at * 1000 : task.created_at * 1000)}</strong>
                      </div>
                    </div>
                    <div className="mobile-record-section">
                      <div>{task.message || '-'}</div>
                      {task.error && <div className="text-danger small mt-1 text-break">{task.error}</div>}
                      <JsonSummary value={task.result} />
                    </div>
                    <TaskActionButtons
                      task={task}
                      expanded={expanded}
                      retryingTaskId={retryingTaskId}
                      stoppingTaskId={stoppingTaskId}
                      onToggleDetails={toggleTaskDetails}
                      onRetryTask={handleRetryTask}
                      onCancelTask={handleCancelTask}
                    />
                    {expanded && (
                      <div className="task-detail-grid mobile-task-detail-grid">
                        <JsonBlock label="结果" value={task.result} />
                        <JsonBlock label="错误" value={task.error} />
                        <JsonBlock label="上下文" value={metadata} />
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="table-responsive">
            <table className="table table-hover mb-0">
              <thead className="table-light">
                <tr>
                  <th>任务</th>
                  <th style={{ width: '120px' }}>类型</th>
                  <th style={{ width: '110px' }}>状态</th>
                  <th style={{ width: '110px' }}>进度</th>
                  <th>消息</th>
                  <th style={{ width: '170px' }}>更新时间</th>
                  <th style={{ width: '150px' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(task => {
                  const expanded = expandedTaskIds.has(task.task_id);
                  const metadata = getTaskMetadata(task);
                  return (
                    <React.Fragment key={task.task_id}>
                      <tr>
                        <td className={task.task_id === focusedTaskId ? 'task-focused-cell' : ''}>
                          <div className="fw-semibold">{task.title || getTaskTypeLabel(task.type)}</div>
                          <div className="small text-muted text-break">{task.task_id}</div>
                        </td>
                        <td>{getTaskTypeLabel(task.type)}</td>
                        <td><StatusBadge status={task.status} /></td>
                        <td className="small text-muted">{formatProgress(task)}</td>
                        <td>
                          <div>{task.message || '-'}</div>
                          {task.error && <div className="text-danger small mt-1">{task.error}</div>}
                          <JsonSummary value={task.result} />
                        </td>
                        <td className="small text-muted">{formatDateTime(task.updated_at ? task.updated_at * 1000 : task.created_at * 1000)}</td>
                        <td>
                          <TaskActionButtons
                            task={task}
                            expanded={expanded}
                            retryingTaskId={retryingTaskId}
                            stoppingTaskId={stoppingTaskId}
                            onToggleDetails={toggleTaskDetails}
                            onRetryTask={handleRetryTask}
                            onCancelTask={handleCancelTask}
                          />
                        </td>
                      </tr>
                      {expanded && (
                        <tr className="task-detail-row">
                          <td colSpan={7}>
                            <div className="task-detail-grid">
                              <JsonBlock label="结果" value={task.result} />
                              <JsonBlock label="错误" value={task.error} />
                              <JsonBlock label="上下文" value={metadata} />
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
            </div>
          )}
        </Panel>
      )}

      {!loading && total > pageSize && (
        <div className="d-flex justify-content-center align-items-center gap-2 my-4">
          <button className="btn btn-outline-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))}>
            上一页
          </button>
          <span className="text-muted small">第 {page} / {totalPages} 页，共 {total} 条</span>
          <button className="btn btn-outline-secondary btn-sm" disabled={page >= totalPages} onClick={() => setPage(value => value + 1)}>
            下一页
          </button>
        </div>
      )}
    </div>
  );
}

export default TasksPage;
