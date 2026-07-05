import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import SearchCommandBar from '../components/home/SearchCommandBar';
import PosterWallSection from '../components/home/PosterWallSection';
import SearchResultsList from '../components/home/SearchResultsList';
import TaskProgressStrip from '../components/home/TaskProgressStrip';
import MessageDetailModal from '../components/MessageDetailModal';
import { PageHeader } from '../components/ui';
import { useHomeSearch } from '../hooks/useHomeSearch';

function HomePage() {
  const home = useHomeSearch();
  const [pageInput, setPageInput] = useState('');
  const showBlockingLoading = home.loading && (home.mode !== 'local' || home.results.length === 0);
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
        eyebrow="Resource Search"
        title="媒体资源搜索"
        description="从 TMDB 海报墙进入 PanSou 搜索，优先发现 115 分享链接并直接转存。"
      />

      <SearchCommandBar
        keyword={home.keyword}
        searchContext={home.searchContext}
        isComposing={home.isComposing}
        loading={home.loading}
        mode={home.mode}
        viewMode={home.viewMode}
        cloudTypes={home.cloudTypes}
        channels={home.channels}
        selectedChannels={home.selectedChannels}
        localSourceFilter={home.localSourceFilter}
        showFilters={home.showFilters}
        showManagement={home.showManagement}
        searchMeta={home.searchMeta}
        total={home.total}
        scraping={home.scraping}
        onKeywordChange={home.setKeyword}
        onSearchContextChange={home.setSearchContext}
        onComposingChange={home.setIsComposing}
        onSearch={() => home.runSearch({ forceRefresh: false, nextPage: 1 })}
        onRefresh={() => home.runSearch({
          forceRefresh: home.mode === 'public',
          nextPage: home.mode === 'local' ? home.page : 1,
        })}
        onModeChange={home.setMode}
        onViewModeChange={home.setViewMode}
        onToggleFilters={() => home.setShowFilters(value => !value)}
        onToggleManagement={() => home.setShowManagement(value => !value)}
        onToggleCloudType={home.toggleCloudType}
        onToggleChannel={home.toggleChannel}
        onClearChannels={() => home.setSelectedChannels([])}
        onScrapeAll={home.handleScrapeAll}
        onMatchPosters={home.matchPosters}
        onClearMessages={home.clearMessages}
        onRefreshChannel={home.handleRefreshChannel}
        onRetryMissing={home.handleRetryMissing}
      />

      {home.mode === 'public' && !home.keyword.trim() && (
        <PosterWallSection
          posterWall={home.posterWall}
          posterCategory={home.posterCategory}
          posterLoading={home.posterLoading}
          onCategoryChange={(value) => {
            home.setPosterCategory(value);
            home.fetchPosterWall(value);
          }}
          onSearchPoster={home.searchPoster}
        />
      )}

      <TaskProgressStrip
        task={home.activeTask}
        onCancel={home.cancelActiveTask}
        cancelling={home.cancellingTaskId === home.activeTask?.task_id}
      />

      {home.searchMeta?.failed_channels?.length > 0 && (
        <div className="alert alert-warning py-2">
          部分频道搜索失败：{home.searchMeta.failed_channels.map(item => item.channel).join(', ')}
        </div>
      )}

      <SearchResultsList
        loading={showBlockingLoading}
        loadingLabel={home.mode === 'local' ? '正在加载本地库...' : '正在搜索...'}
        results={home.results}
        viewMode={home.viewMode}
        mode={home.mode}
        keyword={home.keyword}
        sourceOptions={home.mode === 'local' ? home.localSources : null}
        sourceFilter={home.mode === 'local' ? home.localSourceFilter : undefined}
        onSourceFilterChange={home.mode === 'local' ? home.selectLocalSource : undefined}
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

export default HomePage;
