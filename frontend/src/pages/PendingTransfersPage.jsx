import React, { useCallback, useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { Check, Clock, Copy, FileText, ShieldCheck, X } from 'lucide-react';
import { EmptyState, IconButton, LoadingState, PageHeader, StatTile, StatusBadge } from '../components/ui';
import { getApiErrorMessage } from '../api/errors';
import { confirmPendingTransferLibrary, getPendingTransfers, resolvePendingTransfer } from '../api/transfers';
import { resolveMessageTitle } from '../utils/messageTitle';
import { formatDateTime } from '../utils/text';

const STATUS_OPTIONS = [
  ['pending', '待审核'],
  ['approved', '已提交'],
  ['resolved', '已确认'],
  ['rejected', '已拒绝'],
];

const REASON_OPTIONS = [
  ['all', '全部原因'],
  ['low_confidence', '低于自动阈值'],
  ['manual_review', '人工审核'],
  ['missing_year', '年份缺失'],
  ['weak_title_match', '标题证据不足'],
  ['ambiguous_episode', '集数不明确'],
  ['weak_evidence', '证据不足'],
  ['post_transfer_library_missing', '转存后未入库'],
];

const CONFIDENCE_OPTIONS = [
  ['all', '全部置信度'],
  ['lt60', '低于 60%'],
  ['60to80', '60%-80%'],
  ['gte80', '80% 以上'],
];

const SORT_OPTIONS = [
  ['latest', '最新入队'],
  ['confidence_asc', '置信度低到高'],
  ['confidence_desc', '置信度高到低'],
  ['reason', '入队原因'],
];

function confidenceParams(value) {
  if (value === 'lt60') return { confidence_max: 0.5999 };
  if (value === '60to80') return { confidence_min: 0.6, confidence_max: 0.8 };
  if (value === 'gte80') return { confidence_min: 0.8 };
  return {};
}

function percent(value) {
  if (value === null || value === undefined) return '-';
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function statusTone(status) {
  if (status === 'resolved') return 'success';
  if (status === 'approved') return 'submitted';
  if (status === 'rejected') return 'skipped';
  return 'warning';
}

function statusLabel(status) {
  if (status === 'pending') return '待审核';
  if (status === 'approved') return '已提交';
  if (status === 'resolved') return '已确认';
  if (status === 'rejected') return '已拒绝';
  return status || '-';
}

function isLibraryMissingReview(item) {
  return item.review_type === 'library_missing' || item.pending_reason === 'post_transfer_library_missing';
}

function targetText(item) {
  if (item.target_episode) {
    return `S${String(item.target_season || 1).padStart(2, '0')}E${String(item.target_episode).padStart(2, '0')}`;
  }
  return item.subscription_media_type === 'tv' ? '下一集目标' : '整部资源';
}

function evidenceLabel(key, value) {
  const labels = {
    title_match: {
      full: '标题完整命中',
      alias: '标题命中别名',
      partial: '标题部分命中',
      description: '描述命中',
      none: '标题未命中',
    },
    year_match: {
      matched: '年份匹配',
      missing: '年份缺失',
      not_required: '无年份要求',
    },
    episode_match: {
      matched: '集数匹配',
      ambiguous: '集数不明确',
      not_required: '无集数要求',
      mismatch: '集数不匹配',
    },
  };
  return labels[key]?.[value] || String(value ?? '-');
}

function PendingTransfersPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [reasonFilter, setReasonFilter] = useState('all');
  const [subscriptionFilter, setSubscriptionFilter] = useState('all');
  const [confidenceFilter, setConfidenceFilter] = useState('all');
  const [sortMode, setSortMode] = useState('latest');
  const [expandedId, setExpandedId] = useState(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        status: statusFilter,
        reason: reasonFilter,
        sort: sortMode,
        ...confidenceParams(confidenceFilter),
      };
      if (subscriptionFilter !== 'all') params.subscription_id = Number(subscriptionFilter);
      const response = await getPendingTransfers(params);
      setItems(response.data || []);
    } catch (error) {
      toast.error(getApiErrorMessage(error, '获取审核队列失败'));
    } finally {
      setLoading(false);
    }
  }, [confidenceFilter, reasonFilter, sortMode, statusFilter, subscriptionFilter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const subscriptionOptions = useMemo(() => {
    const map = new Map();
    items.forEach(item => {
      if (item.subscription_id) {
        map.set(String(item.subscription_id), item.subscription_keyword || `订阅 #${item.subscription_id}`);
      }
    });
    return Array.from(map.entries());
  }, [items]);

  const stats = useMemo(() => {
    return items.reduce((acc, item) => {
      acc.total += 1;
      if (item.status === 'pending') acc.pending += 1;
      if (item.status === 'approved') acc.approved += 1;
      if (item.status === 'resolved') acc.resolved += 1;
      if (item.status === 'rejected') acc.rejected += 1;
      return acc;
    }, { total: 0, pending: 0, approved: 0, resolved: 0, rejected: 0 });
  }, [items]);

  const handleAction = async (item, action) => {
    const libraryMissing = isLibraryMissingReview(item);
    const message = action === 'approve'
      ? `确认提交「${resolveMessageTitle(item)}」到 CMS 转存吗？后续结果请在下载历史查看。`
      : libraryMissing
        ? `确认将「${resolveMessageTitle(item)}」标记为未入库吗？订阅状态不会推进。`
        : `确认拒绝「${resolveMessageTitle(item)}」吗？拒绝后该条记录不会再处理。`;
    if (!window.confirm(message)) return;
    setBusyId(item.id);
    try {
      await resolvePendingTransfer(item.id, action);
      toast.success(action === 'approve' ? '已提交转存，可在下载历史查看结果' : libraryMissing ? '已标记为未入库' : '已拒绝');
      await fetchItems();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '操作失败'));
    } finally {
      setBusyId(null);
    }
  };

  const handleConfirmLibrary = async (item) => {
    if (!window.confirm(`确认重新检查 Jellyfin 中的「${resolveMessageTitle(item)}」吗？检测到目标集数后会推进订阅状态。`)) return;
    setBusyId(item.id);
    try {
      await confirmPendingTransferLibrary(item.id);
      toast.success('已确认入库，订阅状态已同步');
      await fetchItems();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Jellyfin 仍未检测到目标集数，未更新订阅状态'));
    } finally {
      setBusyId(null);
    }
  };

  const copyLink = async (link) => {
    if (!link) return toast.error('没有可复制的链接');
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(link);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = link;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      toast.success('链接已复制');
    } catch (error) {
      toast.error('复制失败');
    }
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Review Queue"
        title="订阅审核队列"
        description="订阅命中但不适合自动转存的资源会在提交 CMS 前进入这里，确认后提交转存，拒绝后不再处理。"
      />

      <div className="stat-grid mb-3">
        <StatTile label="当前列表" value={stats.total} icon={ShieldCheck} />
        <StatTile label="待审核" value={stats.pending} tone="warning" icon={Clock} />
        <StatTile label="已提交" value={stats.approved} tone="success" icon={Check} />
        <StatTile label="已确认" value={stats.resolved} tone="success" icon={ShieldCheck} />
        <StatTile label="已拒绝" value={stats.rejected} tone="muted" icon={X} />
      </div>

      <div className="segmented-control compact mb-3">
        {STATUS_OPTIONS.map(([value, label]) => (
          <button key={value} className={statusFilter === value ? 'active' : ''} onClick={() => setStatusFilter(value)}>
            {label}
          </button>
        ))}
      </div>

      <div className="result-controls mb-3">
        <label>
          <span>原因</span>
          <select value={reasonFilter} onChange={(event) => setReasonFilter(event.target.value)}>
            {REASON_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>订阅</span>
          <select value={subscriptionFilter} onChange={(event) => setSubscriptionFilter(event.target.value)}>
            <option value="all">全部订阅</option>
            {subscriptionOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>置信度</span>
          <select value={confidenceFilter} onChange={(event) => setConfidenceFilter(event.target.value)}>
            {CONFIDENCE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>排序</span>
          <select value={sortMode} onChange={(event) => setSortMode(event.target.value)}>
            {SORT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <div className="result-controls-count">{items.length} 条</div>
      </div>

      {loading && <LoadingState label="正在加载审核队列..." />}

      {!loading && items.length === 0 && (
        <EmptyState
          icon={Clock}
          title={statusFilter === 'pending' ? '没有待审核资源' : '当前筛选无记录'}
          description={statusFilter === 'pending' ? '高确定性资源会自动转存，相关但有疑点的资源会出现在这里。' : '调整状态、原因、订阅或置信度筛选后再查看。'}
        />
      )}

      {!loading && items.length > 0 && (
        <div className="compact-results">
          {items.map(item => {
            const evidence = item.review_evidence || {};
            const expanded = expandedId === item.id;
            const libraryMissing = isLibraryMissingReview(item);
            return (
              <article className="compact-result-item review-result-item" key={item.id}>
                <div className="result-main">
                  <div className="result-title-row">
                    <h3>{resolveMessageTitle(item)}</h3>
                    <div className="type-tags">
                      <span>{item.pending_reason_label || '需要审核'}</span>
                      <span>{percent(item.confidence)}</span>
                    </div>
                  </div>
                  <div className="result-meta">
                    <span>{item.subscription_keyword || `订阅 #${item.subscription_id || '-'}`}</span>
                    <span>{targetText(item)}</span>
                    {item.source_label && <span>{item.source_label}</span>}
                    <span>{formatDateTime(item.created_at)}</span>
                    <StatusBadge status={statusTone(item.status)}>
                      {statusLabel(item.status)}
                    </StatusBadge>
                  </div>
                  <div className="review-evidence-strip">
                    {libraryMissing ? (
                      <span>{evidence.message || '订阅转存后的内容未入库，请检查 Jellyfin。'}</span>
                    ) : (
                      <span>置信度 {percent(item.confidence)} / 阈值 {percent(item.subscription_min_confidence)}</span>
                    )}
                    <span>{item.match_reason || '待人工确认'}</span>
                    {(item.risk_flags || []).slice(0, 3).map(flag => <span key={flag} className="risk">{flag}</span>)}
                  </div>
                  {!!(item.quality_tags || []).length && (
                    <div className="review-quality-tags">
                      {(item.quality_tags || []).slice(0, 5).map(tag => <span key={tag}>{tag}</span>)}
                    </div>
                  )}
                  <div className="result-url">{item.link}</div>
                  {expanded && (
                    <div className="pending-transfer-detail">
                      <div className="review-detail-grid">
                        <div><strong>订阅目标：</strong>{item.subscription_keyword || '-'} {item.subscription_year || ''} / {targetText(item)}</div>
                        {libraryMissing ? (
                          <>
                            <div><strong>下载历史：</strong>#{item.library_missing?.history_id || evidence.history_id || '-'}</div>
                            <div><strong>目标集数：</strong>{item.library_missing?.target || evidence.target || targetText(item)}</div>
                            <div><strong>处理建议：</strong>检查 Jellyfin 扫描和命名后再确认入库</div>
                          </>
                        ) : (
                          <>
                            <div><strong>质量要求：</strong>{item.subscription_quality_filter || '不限'}</div>
                            <div><strong>标题证据：</strong>{evidenceLabel('title_match', evidence.title_match)}</div>
                            <div><strong>年份证据：</strong>{evidenceLabel('year_match', evidence.year_match)}</div>
                            <div><strong>集数证据：</strong>{evidenceLabel('episode_match', evidence.episode_match)}</div>
                            <div><strong>自动转存：</strong>{item.subscription_auto_transfer === false ? '关闭' : '开启'}</div>
                          </>
                        )}
                      </div>
                      {item.password && <div><strong>提取码：</strong>{item.password}</div>}
                      {item.payload?.title && <div><strong>原始标题：</strong>{item.payload.title}</div>}
                      {item.payload?.description && <div><strong>描述：</strong>{item.payload.description}</div>}
                      {item.payload?.raw_text && <pre>{item.payload.raw_text}</pre>}
                    </div>
                  )}
                </div>
                <div className="result-actions">
                  <IconButton icon={Copy} className="btn-outline-secondary btn-sm" onClick={() => copyLink(item.link)}>
                    复制链接
                  </IconButton>
                  <IconButton icon={FileText} className="btn-outline-secondary btn-sm" onClick={() => setExpandedId(value => value === item.id ? null : item.id)}>
                    {expanded ? '收起' : '详情'}
                  </IconButton>
                  {item.status === 'pending' && (
                    <>
                      {libraryMissing ? (
                        <IconButton icon={ShieldCheck} className="btn-success btn-sm" disabled={busyId === item.id} onClick={() => handleConfirmLibrary(item)}>
                          确认入库
                        </IconButton>
                      ) : (
                        <IconButton icon={Check} className="btn-success btn-sm" disabled={busyId === item.id} onClick={() => handleAction(item, 'approve')}>
                          提交转存
                        </IconButton>
                      )}
                      <IconButton icon={X} className="btn-outline-danger btn-sm" disabled={busyId === item.id} onClick={() => handleAction(item, 'reject')}>
                        {libraryMissing ? '未入库' : '拒绝'}
                      </IconButton>
                    </>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default PendingTransfersPage;
