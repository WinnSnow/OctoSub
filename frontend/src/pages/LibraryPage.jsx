import React, { useEffect, useRef, useState } from 'react';
import { Archive, ChevronLeft, ChevronRight, FolderSync, Grid3X3, Link2, List, RefreshCcw, Search, Settings2, Sparkles, Trash2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import SearchResultsList from '../components/home/SearchResultsList';
import TaskProgressStrip from '../components/home/TaskProgressStrip';
import MessageDetailModal from '../components/MessageDetailModal';
import { IconButton, PageHeader } from '../components/ui';
import { useHomeSearch } from '../hooks/useHomeSearch';
import { getSearchSourceLabel } from '../utils/media';

function LibraryStatusBar({ keyword, total, searchMeta, onClearKeyword }) {
  return (
    <section className="library-status-bar">
      <div className="library-status-copy">
        <Search size={18} />
        <div>
          <div className="library-status-title">资源库{keyword ? `：${keyword}` : '：全部内容'}</div>
          <div className="library-status-subtitle">
            {keyword ? '由顶部全局搜索筛选资源库内容' : '使用顶部全局搜索选择“资源库”后可按关键词筛选'}
          </div>
        </div>
      </div>
      <div className="library-status-actions">
        {searchMeta && (
          <div className="search-stats">
            <span>{total} 条结果</span>
            <span>{searchMeta.elapsed_ms}ms</span>
            <span>{getSearchSourceLabel(searchMeta.source)}</span>
          </div>
        )}
        {keyword && (
          <button type="button" className="btn btn-outline-secondary btn-sm" onClick={onClearKeyword}>
            清除筛选
          </button>
        )}
      </div>
    </section>
  );
}

function LibraryToolbar({
  loading,
  viewMode,
  showManagement,
  scraping,
  localSourceFilter,
  onRefresh,
  onViewModeChange,
  onToggleManagement,
  onScrapeAll,
  onMatchPosters,
  onClearMessages,
  onRefreshChannel,
  onRetryMissing,
}) {
  const hasLocalSource = Boolean(localSourceFilter && localSourceFilter !== 'all');

  return (
    <section className="library-toolbar">
      <div className="library-toolbar-row">
        <div className="segmented-control compact">
          <button type="button" className={viewMode === 'list' ? 'active' : ''} onClick={() => onViewModeChange('list')}>
            <List size={15} /> 列表
          </button>
          <button type="button" className={viewMode === 'grid' ? 'active' : ''} onClick={() => onViewModeChange('grid')}>
            <Grid3X3 size={15} /> 海报
          </button>
        </div>
        <div className="library-toolbar-actions">
          <IconButton icon={RefreshCcw} className="btn-outline-secondary btn-sm" onClick={onRefresh} disabled={loading}>
            刷新列表
          </IconButton>
          <IconButton icon={Settings2} className="btn-outline-secondary btn-sm" onClick={onToggleManagement}>
            管理操作
          </IconButton>
        </div>
      </div>

      {showManagement && (
        <div className="management-panel">
          <div className="management-group">
            <div className="management-group-title">同步来源</div>
            <div className="management-actions">
              <IconButton icon={FolderSync} className="btn-primary btn-sm" onClick={onScrapeAll} disabled={scraping}>同步全部来源</IconButton>
              <IconButton
                icon={FolderSync}
                className="btn-outline-primary btn-sm"
                onClick={() => onRefreshChannel(localSourceFilter)}
                disabled={scraping || !hasLocalSource}
              >
                同步当前来源
              </IconButton>
              {hasLocalSource && <span className="management-source">{localSourceFilter}</span>}
            </div>
          </div>
          <div className="management-group">
            <div className="management-group-title">完善资源</div>
            <div className="management-actions">
              <IconButton icon={Sparkles} className="btn-outline-info btn-sm" onClick={onMatchPosters}>补全海报</IconButton>
              <IconButton
                icon={Link2}
                className="btn-outline-secondary btn-sm"
                onClick={() => onRetryMissing(localSourceFilter)}
                disabled={scraping || !hasLocalSource}
              >
                补全缺失链接
              </IconButton>
            </div>
          </div>
          <div className="management-group danger">
            <div className="management-group-title">清理数据</div>
            <div className="management-actions">
              <IconButton
                icon={Trash2}
                className="btn-outline-danger btn-sm"
                onClick={() => onClearMessages(localSourceFilter)}
                disabled={!hasLocalSource}
              >
                清空当前来源
              </IconButton>
              <IconButton icon={Archive} className="btn-outline-danger btn-sm" onClick={() => onClearMessages()}>清空资源库</IconButton>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function LibraryPage() {
  const home = useHomeSearch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [pageInput, setPageInput] = useState('');
  const lastAppliedKeywordRef = useRef(null);
  const urlKeyword = searchParams.get('q') || '';
  const normalizedUrlKeyword = urlKeyword.trim();
  const showBlockingLoading = home.loading && home.results.length === 0;
  const {
    mode,
    setMode,
    setKeyword,
    setSearchContext,
    runSearch,
  } = home;

  useEffect(() => {
    if (mode !== 'local') {
      setMode('local');
    }
  }, [mode, setMode]);

  useEffect(() => {
    if (mode !== 'local') return;
    if (lastAppliedKeywordRef.current === normalizedUrlKeyword) return;
    lastAppliedKeywordRef.current = normalizedUrlKeyword;
    setKeyword(normalizedUrlKeyword);
    setSearchContext(null);
    runSearch({ nextPage: 1, overrideKeyword: normalizedUrlKeyword });
  }, [mode, normalizedUrlKeyword, runSearch, setKeyword, setSearchContext]);

  const clearKeyword = () => {
    navigate('/library');
  };

  const jumpToPage = () => {
    const parsed = Number.parseInt(pageInput, 10);
    if (!Number.isFinite(parsed)) return;
    const bounded = Math.max(1, Math.min(parsed, home.localPagination.totalPages));
    setPageInput('');
    home.goToLocalPage(bounded);
  };

  return (
    <div className="search-workspace fade-in">
      <PageHeader
        eyebrow="Resource Library"
        title="资源库"
        description="集中查看、筛选和维护已抓取的本地资源。"
      />

      <LibraryStatusBar
        keyword={normalizedUrlKeyword}
        total={home.total}
        searchMeta={home.searchMeta}
        onClearKeyword={clearKeyword}
      />

      <LibraryToolbar
        loading={home.loading}
        viewMode={home.viewMode}
        showManagement={home.showManagement}
        scraping={home.scraping}
        localSourceFilter={home.localSourceFilter}
        onRefresh={() => home.runSearch({ nextPage: home.page })}
        onViewModeChange={home.setViewMode}
        onToggleManagement={() => home.setShowManagement(value => !value)}
        onScrapeAll={home.handleScrapeAll}
        onMatchPosters={home.matchPosters}
        onClearMessages={home.clearMessages}
        onRefreshChannel={home.handleRefreshChannel}
        onRetryMissing={home.handleRetryMissing}
      />

      <TaskProgressStrip
        task={home.activeTask}
        onCancel={home.cancelActiveTask}
        cancelling={home.cancellingTaskId === home.activeTask?.task_id}
      />

      <SearchResultsList
        loading={showBlockingLoading}
        loadingLabel="正在加载资源库..."
        results={home.results}
        viewMode={home.viewMode}
        mode="local"
        keyword={home.keyword}
        sourceOptions={home.localSources}
        sourceFilter={home.localSourceFilter}
        onSourceFilterChange={home.selectLocalSource}
        onCopyText={home.copyText}
        onForwardLink={home.forwardLink}
        onOpenDetail={home.openDetail}
        onRetry={() => home.runSearch({ forceRefresh: true, nextPage: home.page })}
      />

      {home.localPagination.visible && (
        <div className="d-flex justify-content-center align-items-center gap-2 my-4">
          <button
            type="button"
            className="btn btn-outline-secondary d-inline-flex align-items-center gap-1"
            disabled={home.loading || !home.localPagination.hasPrevious}
            onClick={() => home.goToLocalPage(home.localPagination.page - 1)}
          >
            <ChevronLeft size={16} />
            上一页
          </button>
          <span className="text-muted small">
            第 {home.localPagination.page} / {home.localPagination.totalPages} 页
          </span>
          <div className="input-group input-group-sm" style={{ width: 120 }}>
            <input
              type="number"
              min="1"
              max={home.localPagination.totalPages}
              className="form-control"
              value={pageInput}
              placeholder="页码"
              onChange={event => setPageInput(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') jumpToPage();
              }}
            />
            <button
              type="button"
              className="btn btn-outline-secondary"
              disabled={home.loading || !pageInput}
              onClick={jumpToPage}
            >
              跳转
            </button>
          </div>
          <button
            type="button"
            className="btn btn-outline-secondary d-inline-flex align-items-center gap-1"
            disabled={home.loading || !home.localPagination.hasNext}
            onClick={() => home.goToLocalPage(home.localPagination.page + 1)}
          >
            下一页
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      <MessageDetailModal show={home.showModal} onClose={() => home.setShowModal(false)} message={home.selectedMessage} />
    </div>
  );
}

export default LibraryPage;
