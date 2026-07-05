import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, Download, RefreshCcw, Send } from 'lucide-react';
import { EmptyState, IconButton, LoadingState, PageHeader, Panel, StatTile, StatusBadge } from '../components/ui';
import { useDownloadHistoryData } from '../hooks/useDownloadHistoryData';
import { useDownloadHistoryTasks } from '../hooks/useDownloadHistoryTasks';
import { useIsNarrowViewport } from '../hooks/useViewport';
import { getMediaTypeLabel } from '../utils/media';
import { formatDateTime } from '../utils/text';
import { summarizeTransferFailure, transferFailureDetail } from '../utils/transferStatus';

function TransferFailureNotice({ item }) {
  if (item.status !== 'failed') return null;
  const summary = summarizeTransferFailure(item.callback_message);
  const detail = transferFailureDetail(item.callback_message);
  return (
    <div className="transfer-failure-notice" role="alert">
      <div className="transfer-failure-title">
        <AlertTriangle size={14} />
        {summary}
      </div>
      {detail && detail !== summary && (
        <div className="transfer-failure-detail">{detail}</div>
      )}
    </div>
  );
}

function DownloadHistoryPage() {
  const isMobile = useIsNarrowViewport();
  const [selectedSubscription, setSelectedSubscription] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const pageSize = 100;
  const {
    history,
    subscriptions,
    loading,
    total,
    stats,
    fetchHistory,
    resetToFirstPage,
  } = useDownloadHistoryData({
    page,
    pageSize,
    selectedSubscription,
    statusFilter,
    setPage,
  });
  const {
    syncing,
    retryingHistoryId,
    handleSyncCms,
    handleRetryTransfer,
  } = useDownloadHistoryTasks({
    fetchHistory,
    resetToFirstPage,
  });

  const getSubscriptionName = (subId) => {
    const sub = subscriptions.find(s => s.id === subId);
    return sub ? sub.keyword : `订阅 #${subId}`;
  };

  const getStatusBadge = (status) => {
    return <StatusBadge status={status} />;
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Download History"
        title="下载历史"
        description="查看订阅资源的转存结果、跳过记录和失败状态。"
        actions={(
          <div className="d-flex gap-2">
            <IconButton icon={Send} className="btn-outline-secondary" onClick={handleSyncCms} disabled={syncing}>
              {syncing ? '同步中...' : '同步 CMS'}
            </IconButton>
            <IconButton icon={RefreshCcw} className="btn-outline-primary" onClick={fetchHistory}>
              刷新
            </IconButton>
          </div>
        )}
      />

      <div className="stat-grid mb-3">
        <StatTile label="总记录数" value={stats.total} icon={Download} tone="primary" />
        <StatTile label="已提交" value={stats.submitted} icon={Send} tone="warning" />
        <StatTile label="转存成功" value={stats.success} icon={CheckCircle2} tone="success" />
        <StatTile label="转存失败" value={stats.failed} icon={AlertTriangle} tone="danger" />
        <StatTile label="已跳过" value={stats.skipped} icon={Clock3} />
      </div>

      <Panel className="mb-3">
          <div className="row g-3">
            <div className="col-md-6">
              <label className="form-label small">筛选订阅</label>
              <select
                className="form-select"
                value={selectedSubscription || ''}
                onChange={(e) => {
                  setSelectedSubscription(e.target.value ? parseInt(e.target.value) : null);
                  setPage(1);
                }}
              >
                <option value="">全部订阅</option>
                {subscriptions.map(sub => (
                  <option key={sub.id} value={sub.id}>
                    {sub.keyword} ({getMediaTypeLabel(sub.media_type)})
                  </option>
                ))}
              </select>
            </div>
            <div className="col-md-6">
              <label className="form-label small">筛选状态</label>
              <select
                className="form-select"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="all">全部状态</option>
                <option value="submitted">已提交</option>
                <option value="success">成功</option>
                <option value="failed">失败</option>
                <option value="skipped">跳过</option>
              </select>
            </div>
          </div>
      </Panel>

      {loading && (
        <LoadingState label="正在加载下载历史..." />
      )}

      {!loading && history.length === 0 && (
        <EmptyState
          icon={Download}
          title="暂无下载历史"
          description={history.length === 0 ? '系统还没有处理过任何订阅资源。' : '当前筛选条件下没有记录。'}
        />
      )}

      {!loading && history.length > 0 && (
        <Panel compact>
            {isMobile ? (
              <div className="mobile-record-list history-mobile-list">
                {history.map((item) => (
                  <article className="mobile-record-card history-mobile-card" key={item.id}>
                    <div className="mobile-record-head">
                      <div className="min-w-0">
                        <div className="mobile-record-title">{item.title || '未知资源'}</div>
                        <div className="small text-muted">ID #{item.id}</div>
                      </div>
                      {getStatusBadge(item.status)}
                    </div>

                    <div className="mobile-record-meta">
                      {item.subscription_id ? (
                        <span className="badge bg-primary">{getSubscriptionName(item.subscription_id)}</span>
                      ) : (
                        <span className="text-muted small">无订阅关联</span>
                      )}
                      <span className="text-muted small">{formatDateTime(item.created_at)}</span>
                    </div>

                    <div className="mobile-record-section">
                      <div className="mobile-record-label">指纹</div>
                      <code className="small mobile-code-block">{item.fingerprint}</code>
                    </div>

                    <div className="mobile-record-section">
                      <div className="mobile-record-label">资源链接</div>
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="small text-break"
                      >
                        {item.link}
                      </a>
                      {item.callback_message && (
                        <div className="history-callback-message">
                          {item.callback_message}
                        </div>
                      )}
                      <TransferFailureNotice item={item} />
                    </div>

                    <div className="mobile-record-actions">
                      {item.status === 'failed' ? (
                        <button
                          type="button"
                          className="btn btn-outline-secondary btn-sm"
                          disabled={retryingHistoryId === item.id}
                          onClick={() => handleRetryTransfer(item)}
                        >
                          {retryingHistoryId === item.id ? '重试中...' : '重试转存'}
                        </button>
                      ) : (
                        <span className="text-muted small">暂无可用操作</span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="table-responsive">
              <table className="table table-hover mb-0">
                <thead className="table-light">
                  <tr>
                    <th style={{ width: '50px' }}>ID</th>
                    <th>订阅</th>
                    <th>资源名称</th>
                    <th>指纹</th>
                    <th>资源链接</th>
                    <th style={{ width: '80px' }}>状态</th>
                    <th>处理时间</th>
                    <th style={{ width: '96px' }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item) => (
                    <tr key={item.id}>
                      <td className="text-muted small">{item.id}</td>
                      <td>
                        {item.subscription_id ? (
                          <span className="badge bg-primary">
                            {getSubscriptionName(item.subscription_id)}
                          </span>
                        ) : (
                          <span className="text-muted">-</span>
                        )}
                      </td>
                      <td>
                        <div className="fw-semibold">
                          {item.title || '未知资源'}
                        </div>
                      </td>
                      <td>
                        <code className="small">{item.fingerprint}</code>
                      </td>
                      <td>
                        <div className="text-truncate" style={{ maxWidth: '300px' }}>
                          <a
                            href={item.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-decoration-none small"
                          >
                            {item.link}
                          </a>
                        </div>
                        {item.callback_message && (
                          <div className="history-callback-message">
                            {item.callback_message}
                          </div>
                        )}
                        <TransferFailureNotice item={item} />
                      </td>
                      <td>{getStatusBadge(item.status)}</td>
                      <td className="text-muted small">
                        {formatDateTime(item.created_at)}
                      </td>
                      <td>
                        {item.status === 'failed' ? (
                          <button
                            type="button"
                            className="btn btn-outline-secondary btn-sm"
                            disabled={retryingHistoryId === item.id}
                            onClick={() => handleRetryTransfer(item)}
                          >
                            {retryingHistoryId === item.id ? '重试中...' : '重试转存'}
                          </button>
                        ) : (
                          <span className="text-muted small">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
        </Panel>
      )}

      {!loading && total > pageSize && (
        <div className="d-flex justify-content-center align-items-center gap-2 my-4">
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage(value => Math.max(1, value - 1))}
          >
            上一页
          </button>
          <span className="text-muted small">
            第 {page} / {Math.max(1, Math.ceil(total / pageSize))} 页，共 {total} 条
          </span>
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm"
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage(value => value + 1)}
          >
            下一页
          </button>
        </div>
      )}

      <div className="alert alert-info mt-4">
        <h6 className="alert-heading">状态说明</h6>
        <ul className="mb-0 small">
          <li><strong className="text-success">成功</strong>：资源已成功转存到115网盘</li>
          <li><strong className="text-warning">已提交</strong>：CMS 已接收任务，正在等待最终转存结果</li>
          <li><strong className="text-danger">失败</strong>：转存过程中发生错误</li>
          <li><strong className="text-secondary">跳过</strong>：资源已存在于 Jellyfin 媒体库或之前已下载</li>
        </ul>
      </div>
    </div>
  );
}

export default DownloadHistoryPage;
