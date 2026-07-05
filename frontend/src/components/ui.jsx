import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Film,
  Loader2,
  Search,
  XCircle,
} from 'lucide-react';
import { formatLibraryStateText } from '../utils/media';

export function PageHeader({ eyebrow, title, description, actions, meta }) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {(actions || meta) && (
        <div className="page-header-side">
          {meta}
          {actions && <div className="page-actions">{actions}</div>}
        </div>
      )}
    </header>
  );
}

export function Panel({ children, className = '', compact = false, ...props }) {
  return (
    <section className={`ui-panel ${compact ? 'ui-panel-compact' : ''} ${className}`.trim()} {...props}>
      {children}
    </section>
  );
}

export function StatTile({ label, value, tone = 'neutral', icon: Icon }) {
  return (
    <div className={`stat-tile tone-${tone}`}>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
      {Icon && (
        <div className="stat-icon">
          <Icon size={18} />
        </div>
      )}
    </div>
  );
}

export function EmptyState({ title, description, icon: Icon = Search, actions }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <Icon size={24} />
      </div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {actions && <div className="empty-state-actions">{actions}</div>}
    </div>
  );
}

export function LoadingState({ label = '加载中...' }) {
  return (
    <div className="loading-state">
      <Loader2 className="spin" size={24} />
      <span>{label}</span>
    </div>
  );
}

export function StatusBadge({ status, children }) {
  const config = {
    success: { icon: CheckCircle2, label: '成功', className: 'success' },
    failed: { icon: XCircle, label: '失败', className: 'danger' },
    submitted: { icon: Loader2, label: '已提交', className: 'warning' },
    skipped: { icon: Clock3, label: '跳过', className: 'muted' },
    queued: { icon: Clock3, label: '排队中', className: 'warning' },
    running: { icon: Loader2, label: '运行中', className: 'warning' },
    cancel_requested: { icon: Clock3, label: '停止中', className: 'warning' },
    cancelled: { icon: XCircle, label: '已停止', className: 'muted' },
    active: { icon: Loader2, label: '订阅中', className: 'warning' },
    completed: { icon: CheckCircle2, label: '已完成', className: 'success' },
    partial: { icon: Clock3, label: '部分入库', className: 'warning' },
    missing: { icon: AlertTriangle, label: '未入库', className: 'danger' },
    partial_library: { icon: Clock3, label: '部分入库', className: 'warning' },
    paused: { icon: Clock3, label: '已暂停', className: 'muted' },
    connected: { icon: CheckCircle2, label: '正常', className: 'success' },
    disconnected: { icon: XCircle, label: '异常', className: 'danger' },
    warning: { icon: AlertTriangle, label: '注意', className: 'warning' },
  };
  const item = config[status] || { icon: Film, label: status, className: 'muted' };
  const Icon = item.icon;
  return (
    <span className={`status-badge ${item.className}`}>
      <Icon size={13} />
      {children || item.label}
    </span>
  );
}

export function MediaLibraryStatus({ state, mediaType = null, compact = false }) {
  const text = formatLibraryStateText(state, mediaType);
  if (!text) return null;
  const Icon = text.tone === 'success' ? CheckCircle2 : (text.tone === 'danger' ? AlertTriangle : Clock3);
  return (
    <div className={`library-state-text ${text.tone} ${compact ? 'compact' : ''}`.trim()}>
      <Icon size={compact ? 14 : 16} />
      <div>
        <strong>{text.title}</strong>
        {!compact && <span>{text.detail}</span>}
      </div>
    </div>
  );
}

export function MediaPoster({ src, title, size = 'md' }) {
  return (
    <div className={`media-poster media-poster-${size}`}>
      {src ? (
        <img src={src} alt={title || 'poster'} loading="lazy" />
      ) : (
        <div className="media-poster-empty">
          <Film size={20} />
        </div>
      )}
    </div>
  );
}

export function IconButton({ icon: Icon, children, className = '', ...props }) {
  return (
    <button className={`btn icon-btn ${className}`.trim()} {...props}>
      {Icon && <Icon size={16} />}
      {children && <span>{children}</span>}
    </button>
  );
}
