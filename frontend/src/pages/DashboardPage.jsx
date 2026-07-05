import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Bell,
  CheckCircle2,
  Database,
  Download,
  ListChecks,
  RefreshCcw,
  RotateCcw,
  Save,
  Search,
  Server,
  Settings2,
  GripVertical,
  Tv,
} from 'lucide-react';
import toast from 'react-hot-toast';

import { getDashboardSummary } from '../api/dashboard';
import { getApiErrorMessage } from '../api/errors';
import { EmptyState, IconButton, LoadingState, PageHeader, Panel, StatTile, StatusBadge } from '../components/ui';

const DASHBOARD_PREFERENCES_KEY = 'octosub.dashboardPreferences';

const DASHBOARD_WIDGETS = [
  { key: 'library', label: '本地库组成', defaultWidth: 4 },
  { key: 'subscriptions', label: '订阅进度', defaultWidth: 4 },
  { key: 'downloads', label: '转存进度', defaultWidth: 4 },
  { key: 'runtime', label: '运行状态', defaultWidth: 7 },
  { key: 'tasks', label: '任务状态', defaultWidth: 5 },
  { key: 'summary', label: '系统摘要', defaultWidth: 5 },
  { key: 'recent_tasks', label: '最近任务', defaultWidth: 7 },
  { key: 'quick_links', label: '快捷入口', defaultWidth: 5 },
];

const DEFAULT_DASHBOARD_LAYOUT = 'standard';
const WIDGET_META = Object.fromEntries(DASHBOARD_WIDGETS.map(item => [item.key, item]));
const DEFAULT_DASHBOARD_WIDGETS = DASHBOARD_WIDGETS.map(item => ({ key: item.key, width: item.defaultWidth }));
const BALANCED_DASHBOARD_WIDGETS = [
  { key: 'library', width: 4 },
  { key: 'subscriptions', width: 4 },
  { key: 'downloads', width: 4 },
  { key: 'runtime', width: 8 },
  { key: 'tasks', width: 4 },
  { key: 'recent_tasks', width: 8 },
  { key: 'summary', width: 4 },
  { key: 'quick_links', width: 12 },
];
const DASHBOARD_LAYOUT_OPTIONS = [
  ['standard', '标准'],
  ['balanced', '整齐布局'],
  ['compact', '紧凑'],
  ['monitor', '重点监控'],
];
const WIDGET_WIDTHS = [3, 4, 5, 6, 7, 8, 12];
const DEFAULT_PREFERENCES = {
  theme: 'system',
  default_landing: '/',
  compact_tables: false,
  dashboard_layout: DEFAULT_DASHBOARD_LAYOUT,
  dashboard_widgets: DEFAULT_DASHBOARD_WIDGETS,
};

function numberValue(value) {
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString() : '0';
}

function safeNumber(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function percentValue(value, total) {
  const nextTotal = safeNumber(total);
  if (nextTotal <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((safeNumber(value) / nextTotal) * 100)));
}

function taskStatusLabel(status) {
  const labels = {
    queued: '排队',
    running: '运行',
    completed: '完成',
    failed: '失败',
    cancelled: '取消',
    cancel_requested: '停止中',
  };
  return labels[status] || status || '-';
}

function taskBadgeStatus(status) {
  if (status === 'completed') return 'completed';
  if (status === 'failed') return 'failed';
  if (status === 'cancelled') return 'cancelled';
  if (status === 'running') return 'running';
  return 'queued';
}

function statusLabel(status) {
  const labels = {
    connected: '正常',
    ok: '正常',
    warning: '注意',
    disconnected: '异常',
  };
  return labels[status] || status || '-';
}

function normalizeDashboardPreferences(preferences = {}) {
  const layout = ['standard', 'balanced', 'compact', 'monitor'].includes(preferences.dashboard_layout)
    ? preferences.dashboard_layout
    : DEFAULT_DASHBOARD_LAYOUT;
  const incomingWidgets = Array.isArray(preferences.dashboard_widgets)
    ? preferences.dashboard_widgets
    : DEFAULT_DASHBOARD_WIDGETS;
  const seen = new Set();
  const widgets = incomingWidgets.reduce((acc, item) => {
    const key = typeof item === 'string' ? item : item?.key;
    if (!WIDGET_META[key] || seen.has(key)) return acc;
    const width = Number(typeof item === 'string' ? WIDGET_META[key].defaultWidth : item?.width);
    acc.push({ key, width: WIDGET_WIDTHS.includes(width) ? width : WIDGET_META[key].defaultWidth });
    seen.add(key);
    return acc;
  }, []);
  return {
    ...DEFAULT_PREFERENCES,
    ...preferences,
    dashboard_layout: layout,
    dashboard_widgets: widgets.length ? widgets : DEFAULT_DASHBOARD_WIDGETS,
  };
}

function readStoredDashboardPreferences() {
  if (typeof window === 'undefined') return DEFAULT_PREFERENCES;
  try {
    const stored = window.localStorage.getItem(DASHBOARD_PREFERENCES_KEY);
    return stored ? JSON.parse(stored) : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function saveStoredDashboardPreferences(preferences) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(DASHBOARD_PREFERENCES_KEY, JSON.stringify(preferences));
}

function widgetEnabled(preferences, key) {
  return preferences.dashboard_widgets.some(item => item.key === key);
}

function widgetWidth(preferences, key) {
  const widget = preferences.dashboard_widgets.find(item => item.key === key);
  return widget?.width || WIDGET_META[key]?.defaultWidth || 4;
}

function formatDateTime(value) {
  if (!value) return '暂无同步记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function QuickLink({ to, icon: Icon, title, description }) {
  return (
    <Link to={to} className="dashboard-quick-link">
      <span className="dashboard-quick-icon"><Icon size={18} /></span>
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
    </Link>
  );
}

function jellyfinMessage(check) {
  if (check?.connected) return check.message || '连接成功';
  if (check?.configured) return check.message || '已配置，连接失败';
  return check?.message || 'Jellyfin 未配置';
}

function DonutChart({ title, value, total, label, tone = 'primary' }) {
  const percent = percentValue(value, total);
  const style = { '--chart-percent': `${percent}%` };
  return (
    <div className={`dashboard-donut-card tone-${tone}`}>
      <div className="dashboard-donut" style={style}>
        <span>{percent}%</span>
      </div>
      <div>
        <h5>{title}</h5>
        <strong>{numberValue(value)} / {numberValue(total)}</strong>
        <p>{label}</p>
      </div>
    </div>
  );
}

function JellyfinIndexChart({ library }) {
  const values = [
    { label: '电影', value: safeNumber(library?.jellyfin_movies), tone: 'primary' },
    { label: '剧集', value: safeNumber(library?.jellyfin_series), tone: 'success' },
    { label: '单集', value: safeNumber(library?.jellyfin_episodes), tone: 'warning' },
  ];
  const max = Math.max(...values.map(item => item.value), 1);
  return (
    <div className="dashboard-jellyfin-index">
      <div className="dashboard-mini-title">
        <strong>媒体库组成</strong>
        <span>总计 {numberValue(library?.jellyfin_items)}</span>
      </div>
      <div className="dashboard-bar-stack compact">
        {values.map(item => <BarMetric key={item.label} {...item} max={max} />)}
      </div>
      <div className="dashboard-sync-time">最近同步：{formatDateTime(library?.jellyfin_last_sync_at)}</div>
    </div>
  );
}

function BarMetric({ label, value, max, tone = 'primary' }) {
  const width = percentValue(value, max);
  return (
    <div className={`dashboard-bar-metric tone-${tone}`}>
      <div className="dashboard-bar-head">
        <span>{label}</span>
        <strong>{numberValue(value)}</strong>
      </div>
      <div className="dashboard-bar-track">
        <span style={{ width: `${width}%` }}></span>
      </div>
    </div>
  );
}

function LibraryChart({ library }) {
  const values = [
    { label: '本地消息', value: safeNumber(library?.messages), tone: 'primary' },
    { label: '资源链接', value: safeNumber(library?.links), tone: 'warning' },
    { label: 'Jellyfin 索引', value: safeNumber(library?.jellyfin_items), tone: 'success' },
  ];
  const max = Math.max(...values.map(item => item.value), 1);
  return (
    <Panel>
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><Database size={18} /> 本地库组成</h5>
      <div className="dashboard-bar-stack">
        {values.map(item => <BarMetric key={item.label} {...item} max={max} />)}
      </div>
    </Panel>
  );
}

function SubscriptionsWidget({ summary }) {
  return (
    <Panel className="h-100">
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><Bell size={18} /> 订阅进度</h5>
      <DonutChart
        title="启用订阅"
        value={summary?.subscriptions?.active}
        total={summary?.subscriptions?.total}
        label="当前需要持续追踪的订阅"
        tone="success"
      />
    </Panel>
  );
}

function DownloadsWidget({ summary }) {
  return (
    <Panel className="h-100">
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><Download size={18} /> 转存进度</h5>
      <DonutChart
        title="成功转存"
        value={summary?.downloads?.success}
        total={summary?.downloads?.total}
        label={`待审核 ${numberValue(summary?.downloads?.pending_transfers)} 项`}
        tone="warning"
      />
    </Panel>
  );
}

function TaskStatusChart({ tasks }) {
  const recent = tasks?.recent || [];
  const counts = recent.reduce((acc, task) => {
    const key = taskBadgeStatus(task.status);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const items = [
    { key: 'running', label: '运行', tone: 'warning' },
    { key: 'queued', label: '排队', tone: 'primary' },
    { key: 'completed', label: '完成', tone: 'success' },
    { key: 'failed', label: '失败', tone: 'danger' },
    { key: 'cancelled', label: '取消', tone: 'neutral' },
  ].filter(item => counts[item.key]);
  const total = recent.length || 0;

  return (
    <Panel>
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><ListChecks size={18} /> 任务状态</h5>
      {items.length === 0 ? (
        <div className="dashboard-chart-empty">暂无最近任务</div>
      ) : (
        <>
          <div className="dashboard-task-strip">
            {items.map(item => (
              <span
                key={item.key}
                className={`tone-${item.tone}`}
                style={{ width: `${percentValue(counts[item.key], total)}%` }}
                title={`${item.label}: ${counts[item.key]}`}
              ></span>
            ))}
          </div>
          <div className="dashboard-task-legend">
            {items.map(item => <span key={item.key}>{item.label} <strong>{counts[item.key]}</strong></span>)}
          </div>
          <div className="dashboard-task-mini-list">
            {recent.slice(0, 3).map(task => (
              <div key={task.task_id}>
                <span>{task.title || task.type}</span>
                <StatusBadge status={taskBadgeStatus(task.status)}>{taskStatusLabel(task.status)}</StatusBadge>
              </div>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}

function SystemCheckCard({ label, check }) {
  const status = check?.status || 'warning';
  return (
    <div className={`dashboard-status-card status-${status}`}>
      <div>
        <strong>{label}</strong>
        <p>{check?.message || '-'}</p>
      </div>
      <StatusBadge status={status}>{statusLabel(status)}</StatusBadge>
    </div>
  );
}

function RuntimeStatusPanel({ summary }) {
  const checks = summary?.system?.checks || {};
  const checkItems = [
    ['database', '数据库'],
    ['telegram', 'Telegram'],
    ['proxy', '代理'],
    ['cache', '缓存'],
    ['tmdb', 'TMDB'],
    ['scheduler', '调度器'],
  ];
  const jellyfin = checks.jellyfin || {};
  return (
    <Panel>
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><CheckCircle2 size={18} /> 运行状态</h5>
      <div className="dashboard-jellyfin-card">
        <div className="dashboard-jellyfin-icon"><Tv size={20} /></div>
        <div>
          <div className="dashboard-status-title">
            <strong>Jellyfin 状态</strong>
            <StatusBadge status={jellyfin.status || 'warning'}>{statusLabel(jellyfin.status)}</StatusBadge>
          </div>
          <p>{jellyfinMessage(jellyfin)}</p>
          {jellyfin.url && <small>{jellyfin.url}</small>}
          <small>索引项目 {numberValue(summary?.library?.jellyfin_items)}</small>
        </div>
        <Link to="/jellyfin" className="btn btn-outline-secondary btn-sm">Jellyfin</Link>
      </div>
      <JellyfinIndexChart library={summary?.library} />
      <div className="dashboard-status-grid mt-3">
        {checkItems.map(([key, label]) => (
          <SystemCheckCard key={key} label={label} check={checks[key]} />
        ))}
      </div>
    </Panel>
  );
}

function RecentTasksPanel({ recentTasks }) {
  return (
    <Panel compact>
      <div className="dashboard-section-head">
        <h5><ListChecks size={18} /> 最近任务</h5>
        <Link to="/tasks" className="btn btn-outline-secondary btn-sm">任务中心</Link>
      </div>
      {recentTasks.length === 0 ? (
        <div className="p-3">
          <EmptyState icon={ListChecks} title="暂无任务" description="抓取、订阅检查、转存和索引任务会显示在这里。" />
        </div>
      ) : (
        <div className="table-responsive">
          <table className="table align-middle mb-0">
            <thead>
              <tr>
                <th>任务</th>
                <th>状态</th>
                <th>进度</th>
              </tr>
            </thead>
            <tbody>
              {recentTasks.map(task => (
                <tr key={task.task_id}>
                  <td>
                    <div className="fw-medium">{task.title || task.type}</div>
                    <div className="small text-muted">{task.message || task.task_id}</div>
                  </td>
                  <td><StatusBadge status={taskBadgeStatus(task.status)}>{taskStatusLabel(task.status)}</StatusBadge></td>
                  <td>{numberValue(task.current)} / {numberValue(task.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function QuickLinksPanel({ isAdmin }) {
  return (
    <Panel>
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><Activity size={18} /> 快捷入口</h5>
      <div className="dashboard-quick-grid">
        <QuickLink to="/search" icon={Search} title="搜索资源" description="公开搜索和本地库检索" />
        <QuickLink to="/subscriptions" icon={Bell} title="订阅管理" description="追踪剧集和自动检查" />
        <QuickLink to="/history" icon={Download} title="下载历史" description="查看转存结果和重试" />
        <QuickLink to="/tasks" icon={ListChecks} title="任务中心" description="跟踪后台任务进度" />
        {isAdmin && <QuickLink to="/system" icon={Server} title="系统状态" description="检查服务和配置健康" />}
      </div>
    </Panel>
  );
}

function SummaryPanel({ summary }) {
  return (
    <Panel>
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><CheckCircle2 size={18} /> 系统摘要</h5>
      <div className="dashboard-summary-list">
        <div><span>系统状态</span><strong>{summary?.system?.message || summary?.system?.status || '-'}</strong></div>
        <div><span>Jellyfin 索引</span><strong>{numberValue(summary?.library?.jellyfin_items)}</strong></div>
        <div><span>待审核转存</span><strong>{numberValue(summary?.downloads?.pending_transfers)}</strong></div>
        {summary?.admin && <div><span>频道 / 用户</span><strong>{summary.admin.channels} / {summary.admin.users}</strong></div>}
      </div>
    </Panel>
  );
}

function DashboardLayoutPanel({ preferences, busy, onChange, onReset, onSave }) {
  const setLayoutPreset = (layout) => {
    const next = { ...preferences, dashboard_layout: layout };
    if (layout === 'balanced') {
      next.dashboard_widgets = BALANCED_DASHBOARD_WIDGETS;
    }
    onChange(next);
  };
  const setWidget = (key, checked) => {
    const current = preferences.dashboard_widgets;
    const next = checked
      ? [...current, { key, width: WIDGET_META[key].defaultWidth }]
      : current.filter(item => item.key !== key);
    if (next.length === 0) return;
    onChange({ ...preferences, dashboard_widgets: next });
  };
  const setWidgetWidth = (key, width) => {
    onChange({
      ...preferences,
      dashboard_widgets: preferences.dashboard_widgets.map(item => (
        item.key === key ? { ...item, width } : item
      )),
    });
  };
  const moveWidget = (fromKey, toKey) => {
    if (!fromKey || fromKey === toKey) return;
    const widgets = [...preferences.dashboard_widgets];
    const fromIndex = widgets.findIndex(item => item.key === fromKey);
    const toIndex = widgets.findIndex(item => item.key === toKey);
    if (fromIndex < 0 || toIndex < 0) return;
    const [moved] = widgets.splice(fromIndex, 1);
    widgets.splice(toIndex, 0, moved);
    onChange({ ...preferences, dashboard_widgets: widgets });
  };
  const enabledKeys = preferences.dashboard_widgets.map(item => item.key);
  return (
    <Panel className="dashboard-layout-panel">
      <div className="dashboard-layout-head">
        <h5><Settings2 size={18} /> 概览布局</h5>
        <div className="d-flex gap-2 flex-wrap">
          <IconButton icon={RotateCcw} className="btn-outline-secondary btn-sm" onClick={onReset}>默认</IconButton>
          <IconButton icon={Save} className="btn-primary btn-sm" onClick={onSave} disabled={busy}>
            {busy ? '保存中...' : '保存布局'}
          </IconButton>
        </div>
      </div>
      <div className="dashboard-layout-options">
        {DASHBOARD_LAYOUT_OPTIONS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={preferences.dashboard_layout === value ? 'active' : ''}
            onClick={() => setLayoutPreset(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="dashboard-layout-editor">
        <div className="dashboard-widget-order" role="list" aria-label="概览板块排序">
          {preferences.dashboard_widgets.map(item => (
            <div
              key={item.key}
              className="dashboard-widget-order-item"
              role="listitem"
              aria-label={`移动 ${WIDGET_META[item.key]?.label || item.key}`}
              draggable
              onDragStart={(event) => event.dataTransfer.setData('text/plain', item.key)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => moveWidget(event.dataTransfer.getData('text/plain'), item.key)}
            >
              <span className="dashboard-drag-handle" aria-hidden="true"><GripVertical size={16} /></span>
              <strong>{WIDGET_META[item.key]?.label || item.key}</strong>
              <div className="dashboard-width-control" aria-label={`${WIDGET_META[item.key]?.label || item.key} 宽度`}>
                {WIDGET_WIDTHS.map(width => (
                  <button
                    key={width}
                    type="button"
                    className={item.width === width ? 'active' : ''}
                    onClick={() => setWidgetWidth(item.key, width)}
                  >
                    {width}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="dashboard-widget-options">
          {DASHBOARD_WIDGETS.map(item => (
            <label key={item.key}>
              <input
                type="checkbox"
                checked={enabledKeys.includes(item.key)}
                onChange={(event) => setWidget(item.key, event.target.checked)}
              />
              <span>{item.label}</span>
            </label>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function renderDashboardWidget(key, summary, recentTasks, isAdmin) {
  const components = {
    library: <LibraryChart library={summary?.library} />,
    subscriptions: <SubscriptionsWidget summary={summary} />,
    downloads: <DownloadsWidget summary={summary} />,
    runtime: <RuntimeStatusPanel summary={summary} />,
    tasks: <TaskStatusChart tasks={summary?.tasks} />,
    recent_tasks: <RecentTasksPanel recentTasks={recentTasks} />,
    quick_links: <QuickLinksPanel isAdmin={isAdmin} />,
    summary: <SummaryPanel summary={summary} />,
  };
  return components[key] || null;
}

function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [layoutOpen, setLayoutOpen] = useState(false);
  const [layoutBusy, setLayoutBusy] = useState(false);
  const [dashboardPreferences, setDashboardPreferences] = useState(() => normalizeDashboardPreferences(readStoredDashboardPreferences()));

  const fetchSummary = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await getDashboardSummary();
      setSummary(response.data);
    } catch (err) {
      setError(getApiErrorMessage(err, '获取概览失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const handleResetLayout = () => {
    setDashboardPreferences(normalizeDashboardPreferences({
      dashboard_layout: DEFAULT_DASHBOARD_LAYOUT,
      dashboard_widgets: DEFAULT_DASHBOARD_WIDGETS,
    }));
  };

  const handleSaveLayout = async () => {
    setLayoutBusy(true);
    try {
      const nextPreferences = normalizeDashboardPreferences(dashboardPreferences);
      saveStoredDashboardPreferences(nextPreferences);
      setDashboardPreferences(nextPreferences);
      toast.success('概览布局已保存');
    } catch (err) {
      toast.error('保存概览布局失败');
    } finally {
      setLayoutBusy(false);
    }
  };

  if (loading) return <LoadingState label="正在加载概览..." />;

  if (error) {
    return (
      <EmptyState
        icon={Activity}
        title="概览加载失败"
        description={error}
        actions={<IconButton icon={RefreshCcw} className="btn-primary" onClick={fetchSummary}>重试</IconButton>}
      />
    );
  }

  const recentTasks = summary?.tasks?.recent || [];
  const isAdmin = true;

  return (
    <div className="fade-in dashboard-page">
      <PageHeader
        eyebrow="Overview"
        title="概览"
        description="查看本地库、订阅、任务和转存状态，并快速进入常用工作流。"
        actions={(
          <>
            <IconButton
              icon={Settings2}
              className={layoutOpen ? 'btn-primary' : 'btn-outline-secondary'}
              onClick={() => setLayoutOpen(!layoutOpen)}
            >
              布局
            </IconButton>
            <IconButton icon={RefreshCcw} className="btn-outline-secondary" onClick={fetchSummary}>刷新</IconButton>
          </>
        )}
      />

      {layoutOpen && (
        <DashboardLayoutPanel
          preferences={dashboardPreferences}
          busy={layoutBusy}
          onChange={setDashboardPreferences}
          onReset={handleResetLayout}
          onSave={handleSaveLayout}
        />
      )}

      <div className="stats-grid mb-3">
        <StatTile label="本地消息" value={numberValue(summary?.library?.messages)} tone="primary" icon={Database} />
        <StatTile label="资源链接" value={numberValue(summary?.library?.links)} tone="neutral" icon={Search} />
        <StatTile label="启用订阅" value={numberValue(summary?.subscriptions?.active)} tone="success" icon={Bell} />
        <StatTile label="成功转存" value={numberValue(summary?.downloads?.success)} tone="warning" icon={Download} />
      </div>

      <div className={`dashboard-widget-grid layout-${dashboardPreferences.dashboard_layout}`}>
        {dashboardPreferences.dashboard_widgets.map(item => (
          <div
            key={item.key}
            className={`dashboard-widget widget-${item.key} span-${widgetWidth(dashboardPreferences, item.key)}`}
          >
            {renderDashboardWidget(item.key, summary, recentTasks, isAdmin)}
          </div>
        ))}
      </div>
    </div>
  );
}

export default DashboardPage;
