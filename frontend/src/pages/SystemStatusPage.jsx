import React, { useCallback, useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  FolderTree,
  HardDrive,
  Layers,
  Network,
  RefreshCcw,
  Server,
  Settings2,
  ShieldCheck,
  ScrollText,
  Tv,
} from 'lucide-react';

import { cleanupSystemCache, getSystemStatus } from '../api/system';
import { getApiErrorMessage } from '../api/errors';
import { EmptyState, IconButton, LoadingState, PageHeader, Panel, StatTile, StatusBadge } from '../components/ui';
import { formatDateTime } from '../utils/text';

const CHECK_LABELS = {
  database: '数据库',
  telegram: 'Telegram',
  proxy: '代理',
  jellyfin: 'Jellyfin',
  cache: '缓存',
  cms: 'CMS',
  tmdb: 'TMDB',
  scheduler: '调度器',
  runtime_paths: '运行路径',
  recent_failed_tasks: '失败任务',
  recent_events: '最近事件',
  configuration: '配置健康',
};

const CHECK_ICONS = {
  database: Database,
  telegram: ShieldCheck,
  proxy: Network,
  jellyfin: Tv,
  cache: Layers,
  cms: Server,
  tmdb: HardDrive,
  scheduler: Clock3,
  runtime_paths: FolderTree,
  recent_failed_tasks: AlertTriangle,
  recent_events: ScrollText,
  configuration: Settings2,
};

function statusToBadge(status) {
  if (status === 'connected') return 'connected';
  if (status === 'warning') return 'warning';
  return 'disconnected';
}

function statusText(status) {
  if (status === 'connected') return '正常';
  if (status === 'warning') return '注意';
  return '异常';
}

function CheckCard({ name, check }) {
  const Icon = CHECK_ICONS[name] || Settings2;
  return (
    <Panel className="system-check-card">
      <div className="system-check-head">
        <div className="system-check-title">
          <Icon size={18} />
          <strong>{CHECK_LABELS[name] || name}</strong>
        </div>
        <StatusBadge status={statusToBadge(check?.status)}>{statusText(check?.status)}</StatusBadge>
      </div>
      <p className="system-check-message">{check?.message || '-'}</p>
      {check?.error && <div className="text-danger small text-break">{check.error}</div>}
    </Panel>
  );
}

function diagnosticStatus(severity) {
  if (severity === 'danger') return 'disconnected';
  if (severity === 'warning') return 'warning';
  return 'connected';
}

function DiagnosticPanel({ items = [] }) {
  if (!items.length) return null;
  return (
    <Panel className="mb-3" compact>
      <div className="system-section-title">
        <span>诊断建议</span>
        <small className="text-muted">根据当前状态自动生成</small>
      </div>
      <div className="system-diagnostics">
        {items.map(item => (
          <div className="system-diagnostic-item" key={`${item.target}-${item.title}`}>
            <div className="system-diagnostic-head">
              <strong>{item.title}</strong>
              <StatusBadge status={diagnosticStatus(item.severity)}>
                {item.severity === 'danger' ? '高' : (item.severity === 'warning' ? '中' : '低')}
              </StatusBadge>
            </div>
            <p>{item.message}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ConfigHealthPanel({ payload }) {
  const items = payload?.items || [];
  if (!items.length) return null;
  return (
    <Panel className="mb-3" compact>
      <div className="system-section-title">
        <span>配置健康</span>
        <small className="text-muted">{payload?.message || '配置摘要'}</small>
      </div>
      <div className="system-config-grid">
        {items.map(item => {
          const status = item.configured ? 'connected' : (item.required ? 'disconnected' : 'warning');
          return (
            <div className="system-config-item" key={item.key}>
              <div className="system-config-head">
                <div>
                  <strong>{item.label}</strong>
                  <span>{item.required ? '必要配置' : '增强配置'}</span>
                </div>
                <StatusBadge status={status}>{item.configured ? '已配置' : '未配置'}</StatusBadge>
              </div>
              <p>{item.capability}</p>
              {!item.configured && <small>{item.hint}</small>}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function RuntimePaths({ items = [] }) {
  if (!items.length) return null;
  return (
    <Panel className="mt-3" compact>
      <div className="system-section-title">运行路径</div>
      <div className="table-responsive responsive-table-scroll">
        <table className="table table-hover mb-0 diagnostic-table">
          <thead className="table-light">
            <tr>
              <th style={{ width: '150px' }}>项目</th>
              <th>路径</th>
              <th style={{ width: '90px' }}>存在</th>
              <th style={{ width: '90px' }}>可写</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.key}>
                <td className="fw-semibold">{item.key}</td>
                <td><code className="text-break">{item.path}</code></td>
                <td><StatusBadge status={item.exists ? 'connected' : 'warning'}>{item.exists ? '是' : '否'}</StatusBadge></td>
                <td><StatusBadge status={item.writable ? 'connected' : 'disconnected'}>{item.writable ? '是' : '否'}</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function SchedulerJobs({ jobs = [] }) {
  return (
    <Panel className="mt-3" compact>
      <div className="system-section-title">调度任务</div>
      {jobs.length === 0 ? (
        <EmptyState icon={Clock3} title="暂无调度任务" description="订阅检查或 CMS 同步启用后会显示在这里。" />
      ) : (
        <div className="table-responsive responsive-table-scroll">
          <table className="table table-hover mb-0 diagnostic-table">
            <thead className="table-light">
              <tr>
                <th>任务</th>
                <th style={{ width: '180px' }}>下次运行</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(job => (
                <tr key={job.id || job.name}>
                  <td>
                    <div className="fw-semibold">{job.name || job.id}</div>
                    <div className="small text-muted">{job.id}</div>
                  </td>
                  <td className="small text-muted">{job.next_run_time || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function FailedTasks({ payload }) {
  const items = payload?.items || [];
  return (
    <Panel className="mt-3" compact>
      <div className="system-section-title">最近失败任务</div>
      {items.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="暂无失败任务" description="最近的后台任务没有失败记录。" />
      ) : (
        <div className="table-responsive responsive-table-scroll">
          <table className="table table-hover mb-0 diagnostic-table">
            <thead className="table-light">
              <tr>
                <th>任务</th>
                <th style={{ width: '130px' }}>类型</th>
                <th>错误</th>
                <th style={{ width: '170px' }}>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {items.map(task => (
                <tr key={task.task_id}>
                  <td>
                    <div className="fw-semibold">{task.title || task.task_id}</div>
                    <div className="small text-muted text-break">{task.task_id}</div>
                  </td>
                  <td>{task.type || '-'}</td>
                  <td className="text-danger small text-break">{task.error || task.message || '-'}</td>
                  <td className="small text-muted">
                    {task.updated_at ? formatDateTime(task.updated_at * 1000) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function RecentEvents({ payload }) {
  const items = payload?.items || [];
  return (
    <Panel className="mt-3" compact>
      <div className="system-section-title">最近事件</div>
      {items.length === 0 ? (
        <EmptyState icon={ScrollText} title="暂无事件" description="结构化任务、搜索和系统事件会显示在这里。" />
      ) : (
        <div className="table-responsive responsive-table-scroll">
          <table className="table table-hover mb-0 diagnostic-table">
            <thead className="table-light">
              <tr>
                <th style={{ width: '170px' }}>事件</th>
                <th>内容</th>
                <th style={{ width: '110px' }}>任务</th>
                <th style={{ width: '170px' }}>时间</th>
              </tr>
            </thead>
            <tbody>
              {items.map((event, index) => (
                <tr key={`${event.event}-${event.ts}-${index}`}>
                  <td className="fw-semibold">{event.event}</td>
                  <td><code className="task-json-summary">{JSON.stringify(event)}</code></td>
                  <td>
                    {event.task_id ? (
                      <a className="btn btn-outline-secondary btn-sm" href={`/tasks?task_id=${encodeURIComponent(event.task_id)}`}>
                        查看任务
                      </a>
                    ) : '-'}
                  </td>
                  <td className="small text-muted">{event.ts ? formatDateTime(event.ts * 1000) : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function CacheStats({ payload, onCleanup, cleaning }) {
  const items = payload?.items || [];
  if (!items.length) return null;
  return (
    <Panel className="mt-3" compact>
      <div className="system-section-title">
        <span>缓存状态</span>
        <div className="d-flex align-items-center gap-2 flex-wrap">
          {payload?.message && <small className="text-muted">{payload.message}</small>}
          <button className="btn btn-outline-secondary btn-sm" onClick={onCleanup} disabled={cleaning || (payload?.expired || 0) <= 0}>
            {cleaning ? '清理中...' : '清理过期'}
          </button>
        </div>
      </div>
      <div className="table-responsive responsive-table-scroll">
        <table className="table table-hover mb-0 diagnostic-table">
          <thead className="table-light">
            <tr>
              <th>缓存表</th>
              <th style={{ width: '100px' }}>有效</th>
              <th style={{ width: '100px' }}>过期</th>
              <th style={{ width: '100px' }}>总数</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.table}>
                <td className="fw-semibold">{item.table}</td>
                <td>{item.active}</td>
                <td className={item.expired > 0 ? 'text-warning' : ''}>{item.expired}</td>
                <td>{item.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function SystemStatusPage() {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cleaningCache, setCleaningCache] = useState(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getSystemStatus();
      setPayload(response.data);
    } catch (error) {
      toast.error(getApiErrorMessage(error, '获取系统状态失败'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleCleanupCache = async () => {
    setCleaningCache(true);
    try {
      const response = await cleanupSystemCache();
      toast.success(`已清理 ${response.data?.deleted || 0} 条过期缓存`);
      await fetchStatus();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '清理缓存失败'));
    } finally {
      setCleaningCache(false);
    }
  };

  const checks = payload?.checks || {};
  const stats = useMemo(() => {
    const values = Object.values(checks);
    return {
      total: values.length,
      ok: values.filter(check => check.status === 'connected').length,
      warning: values.filter(check => check.status === 'warning').length,
      failed: values.filter(check => check.status === 'disconnected').length,
    };
  }, [checks]);

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="System"
        title="系统状态"
        description="快速检查数据库、Telegram、代理、Jellyfin、CMS、TMDB、调度器和运行路径是否正常。"
        meta={payload && <StatusBadge status={statusToBadge(payload.status)}>{statusText(payload.status)}</StatusBadge>}
        actions={(
          <IconButton icon={RefreshCcw} className="btn-outline-primary" onClick={fetchStatus} disabled={loading}>
            刷新
          </IconButton>
        )}
      />

      {loading && !payload && <LoadingState label="正在加载系统状态..." />}

      {payload && (
        <>
          <div className="stat-grid mb-3">
            <StatTile label="检查项" value={stats.total} icon={Settings2} tone="primary" />
            <StatTile label="正常" value={stats.ok} icon={CheckCircle2} tone="success" />
            <StatTile label="注意" value={stats.warning} icon={AlertTriangle} tone="warning" />
            <StatTile label="异常" value={stats.failed} icon={AlertTriangle} tone="danger" />
          </div>

          <div className="system-generated text-muted small mb-3">
            生成时间：{formatDateTime(payload.generated_at * 1000)}
          </div>

          <DiagnosticPanel items={payload.diagnostics || []} />
          <ConfigHealthPanel payload={checks.configuration} />

          <div className="system-check-grid">
            {Object.entries(checks)
              .filter(([name]) => name !== 'runtime_paths' && name !== 'recent_failed_tasks')
              .filter(([name]) => name !== 'recent_events')
              .filter(([name]) => name !== 'cache')
              .filter(([name]) => name !== 'configuration')
              .map(([name, check]) => (
                <CheckCard key={name} name={name} check={check} />
              ))}
          </div>

          <CacheStats payload={checks.cache} onCleanup={handleCleanupCache} cleaning={cleaningCache} />
          <RuntimePaths items={checks.runtime_paths?.items} />
          <SchedulerJobs jobs={checks.scheduler?.jobs} />
          <FailedTasks payload={checks.recent_failed_tasks} />
          <RecentEvents payload={checks.recent_events} />
        </>
      )}
    </div>
  );
}

export default SystemStatusPage;
