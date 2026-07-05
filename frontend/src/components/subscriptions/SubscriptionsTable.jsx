import React from 'react';
import { CheckCircle2, Clapperboard, Edit3, Film, PauseCircle, PlayCircle, RefreshCcw, Trash2 } from 'lucide-react';

import { MediaLibraryStatus, MediaPoster, Panel, StatusBadge } from '../ui';
import { formatDateTime } from '../../utils/text';
import { DEFAULT_SUBSCRIPTION_CONFIDENCE } from '../../config/app';
import { useIsNarrowViewport } from '../../hooks/useViewport';
import { getMediaTypeBadgeClass, getMediaTypeLabel } from '../../utils/media';
import {
  formatAutoSearchTarget,
  formatFutureMissingSummary,
  formatHistoricalMissingSummary,
  formatSubscriptionProgress,
  formatTargetSeasons,
  getSubscriptionStatus,
} from '../../utils/subscriptions';

function LifecycleBadge({ subscription }) {
  const status = getSubscriptionStatus(subscription);
  if (status === 'completed') return <StatusBadge status="completed">已完成</StatusBadge>;
  if (status === 'paused') return <StatusBadge status="paused">已暂停</StatusBadge>;
  return <StatusBadge status="active">启用检查</StatusBadge>;
}

function SubscriptionActions({
  subscription,
  checkingId,
  onEdit,
  onStatusChange,
  onSingleCheck,
  onDelete,
}) {
  return (
    <>
      <button className="btn btn-sm btn-outline-primary" onClick={() => onEdit(subscription)}>
        <Edit3 size={14} /> 编辑
      </button>
      {(getSubscriptionStatus(subscription) === 'paused') && subscription.status !== 'completed' ? (
        <button className="btn btn-sm btn-outline-success" onClick={() => onStatusChange(subscription, 'active')}>
          <PlayCircle size={14} /> 恢复
        </button>
      ) : subscription.status !== 'completed' && (
        <button className="btn btn-sm btn-outline-warning" onClick={() => onStatusChange(subscription, 'paused')}>
          <PauseCircle size={14} /> 停用
        </button>
      )}
      {subscription.status !== 'completed' && (
        <button className="btn btn-sm btn-outline-success" onClick={() => onStatusChange(subscription, 'completed')}>
          <CheckCircle2 size={14} /> 完成
        </button>
      )}
      <button
        className="btn btn-sm btn-outline-secondary"
        onClick={() => onSingleCheck(subscription)}
        disabled={checkingId === subscription.id}
      >
        <RefreshCcw size={14} /> {checkingId === subscription.id ? '检查中' : '检查下一集'}
      </button>
      <button className="btn btn-sm btn-outline-danger" onClick={() => onDelete(subscription.id)}>
        <Trash2 size={14} /> 删除
      </button>
    </>
  );
}

function SubscriptionsTable({
  subscriptions,
  checkingId,
  onEdit,
  onStatusChange,
  onSingleCheck,
  onDelete,
}) {
  const isMobile = useIsNarrowViewport();

  if (isMobile) {
    return (
      <Panel compact>
        <div className="mobile-record-list subscription-mobile-list">
          {subscriptions.map((sub) => (
            <article className="mobile-record-card subscription-mobile-card" key={sub.id}>
              <div className="mobile-record-head">
                <MediaPoster src={sub.poster_url} title={sub.keyword} size="sm" />
                <div className="min-w-0">
                  <div className="mobile-record-title">
                    {sub.keyword}
                    {sub.year && <span className="text-muted ms-1">({sub.year})</span>}
                  </div>
                  <div className="mobile-record-meta">
                    <span className={`badge ${getMediaTypeBadgeClass(sub.media_type)}`}>
                      {sub.media_type === 'tv' ? <Clapperboard size={12} /> : <Film size={12} />} {getMediaTypeLabel(sub.media_type)}
                    </span>
                    {sub.tmdb_id ? <StatusBadge status="success">精准</StatusBadge> : <StatusBadge status="warning">关键词</StatusBadge>}
                  </div>
                </div>
              </div>

              <div className="mobile-record-section">
                <MediaLibraryStatus
                  state={{
                    status: getSubscriptionStatus(sub),
                    media_type: sub.media_type,
                    label: formatSubscriptionProgress(sub),
                    progress_current: sub.progress_current,
                    progress_total: sub.progress_total,
                    completed_at: sub.completed_at,
                  }}
                  mediaType={sub.media_type}
                />
                {formatTargetSeasons(sub) && <div className="small text-primary mt-1">{formatTargetSeasons(sub)}</div>}
                {formatAutoSearchTarget(sub) && <div className="small text-primary mt-1">{formatAutoSearchTarget(sub)}</div>}
                {formatHistoricalMissingSummary(sub) && <div className="small text-muted mt-1">{formatHistoricalMissingSummary(sub)}</div>}
                {formatFutureMissingSummary(sub) && <div className="small text-muted mt-1">{formatFutureMissingSummary(sub)}</div>}
              </div>

              <div className="mobile-record-grid">
                <div>
                  <span>质量过滤</span>
                  <code className="small">{sub.quality_filter || '不限'}</code>
                </div>
                <div>
                  <span>最近检查</span>
                  <strong>{sub.last_checked_at ? formatDateTime(sub.last_checked_at) : '尚未检查'}</strong>
                </div>
                {sub.tmdb_id && (
                  <div>
                    <span>TMDB ID</span>
                    <strong>{sub.tmdb_id}</strong>
                  </div>
                )}
              </div>

              <div className="mobile-record-meta">
                <LifecycleBadge subscription={sub} />
                {!sub.enabled && getSubscriptionStatus(sub) !== 'completed' ? (
                  <StatusBadge status="warning">已停用</StatusBadge>
                ) : sub.auto_transfer ? (
                  <StatusBadge status="success">自动 {Math.round((sub.min_confidence || DEFAULT_SUBSCRIPTION_CONFIDENCE) * 100)}%</StatusBadge>
                ) : (
                  <StatusBadge status="warning">人工确认</StatusBadge>
                )}
              </div>

              <div className="mobile-record-actions">
                <SubscriptionActions
                  subscription={sub}
                  checkingId={checkingId}
                  onEdit={onEdit}
                  onStatusChange={onStatusChange}
                  onSingleCheck={onSingleCheck}
                  onDelete={onDelete}
                />
              </div>
            </article>
          ))}
        </div>
      </Panel>
    );
  }

  return (
    <Panel compact>
      <div className="table-responsive">
        <table className="table table-hover mb-0">
          <thead className="table-light">
            <tr>
              <th style={{ width: '60px' }}></th>
              <th>订阅内容</th>
              <th>类型</th>
              <th>入库进度</th>
              <th>匹配模式</th>
              <th>质量过滤</th>
              <th>自动策略</th>
              <th>最近检查</th>
              <th style={{ width: '230px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => (
              <tr key={sub.id}>
                <td>
                  <MediaPoster src={sub.poster_url} title={sub.keyword} size="sm" />
                </td>
                <td>
                  <strong>{sub.keyword}</strong>
                  {sub.year && <span className="text-muted ms-2">({sub.year})</span>}
                  {sub.tmdb_id && (
                    <div className="small text-muted">TMDB ID: {sub.tmdb_id}</div>
                  )}
                  {formatTargetSeasons(sub) && (
                    <div className="small text-primary">{formatTargetSeasons(sub)}</div>
                  )}
                  <div className="small text-muted">{sub.status === 'completed' ? '已完成后默认隐藏在进行中列表' : '进行中列表会持续跟进缺失内容'}</div>
                </td>
                <td>
                  <span className={`badge ${getMediaTypeBadgeClass(sub.media_type)}`}>
                    {sub.media_type === 'tv' ? <Clapperboard size={12} /> : <Film size={12} />} {getMediaTypeLabel(sub.media_type)}
                  </span>
                </td>
                <td>
                  <MediaLibraryStatus
                    state={{
                      status: getSubscriptionStatus(sub),
                      media_type: sub.media_type,
                      label: formatSubscriptionProgress(sub),
                      progress_current: sub.progress_current,
                      progress_total: sub.progress_total,
                      completed_at: sub.completed_at,
                    }}
                    mediaType={sub.media_type}
                  />
                  {formatAutoSearchTarget(sub) && (
                    <div className="small text-primary mt-1">{formatAutoSearchTarget(sub)}</div>
                  )}
                  {formatHistoricalMissingSummary(sub) && (
                    <div className="small text-muted mt-1">{formatHistoricalMissingSummary(sub)}</div>
                  )}
                  {formatFutureMissingSummary(sub) && (
                    <div className="small text-muted mt-1">{formatFutureMissingSummary(sub)}</div>
                  )}
                </td>
                <td>
                  {sub.tmdb_id ? (
                    <StatusBadge status="success">精准</StatusBadge>
                  ) : (
                    <StatusBadge status="warning">关键词</StatusBadge>
                  )}
                </td>
                <td>
                  <code className="small">{sub.quality_filter || '不限'}</code>
                </td>
                <td>
                  <div className="d-flex flex-wrap gap-1">
                    <LifecycleBadge subscription={sub} />
                    {!sub.enabled && getSubscriptionStatus(sub) !== 'completed' ? (
                      <StatusBadge status="warning">已停用</StatusBadge>
                    ) : sub.auto_transfer ? (
                      <StatusBadge status="success">自动 {Math.round((sub.min_confidence || DEFAULT_SUBSCRIPTION_CONFIDENCE) * 100)}%</StatusBadge>
                    ) : (
                      <StatusBadge status="warning">人工确认</StatusBadge>
                    )}
                  </div>
                </td>
                <td className="small text-muted">
                  {sub.last_checked_at ? formatDateTime(sub.last_checked_at) : '尚未检查'}
                </td>
                <td>
                  <div className="d-flex flex-wrap gap-1">
                    <SubscriptionActions
                      subscription={sub}
                      checkingId={checkingId}
                      onEdit={onEdit}
                      onStatusChange={onStatusChange}
                      onSingleCheck={onSingleCheck}
                      onDelete={onDelete}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export default SubscriptionsTable;
