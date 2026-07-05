import React from 'react';
import { Archive, Filter, FolderSync, Grid3X3, Link2, List, RefreshCcw, Search, Settings2, Sparkles, Trash2 } from 'lucide-react';

import { CLOUD_TYPES, getSearchSourceLabel } from '../../utils/media';
import { IconButton } from '../ui';

function SearchCommandBar({
  keyword,
  searchContext,
  isComposing,
  loading,
  mode,
  viewMode,
  cloudTypes,
  channels,
  selectedChannels,
  localSourceFilter = 'all',
  showFilters,
  showManagement,
  searchMeta,
  total,
  scraping,
  onKeywordChange,
  onSearchContextChange,
  onComposingChange,
  onSearch,
  onRefresh,
  onModeChange,
  onViewModeChange,
  onToggleFilters,
  onToggleManagement,
  onToggleCloudType,
  onToggleChannel,
  onClearChannels,
  onScrapeAll,
  onMatchPosters,
  onClearMessages,
  onRefreshChannel,
  onRetryMissing,
  compact = false,
}) {
  const hasLocalSource = Boolean(localSourceFilter && localSourceFilter !== 'all');
  const refreshLabel = '刷新列表';

  return (
    <section className="search-command">
      <div className="d-flex flex-column flex-xl-row gap-3 align-items-xl-center">
        <div className="flex-grow-1">
          <div className="input-group input-group-lg search-input-group">
            <span className="input-group-text"><Search size={18} /></span>
            <input
              className="form-control"
              value={keyword}
              onChange={(event) => {
                onKeywordChange(event.target.value);
                if (searchContext?.keyword !== event.target.value) onSearchContextChange(null);
              }}
              onCompositionStart={() => onComposingChange(true)}
              onCompositionEnd={() => onComposingChange(false)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.nativeEvent.isComposing && !isComposing) {
                  onSearch();
                }
              }}
              placeholder="搜索电影、剧集、资源关键词"
            />
            <button className="btn btn-primary" onClick={onSearch} disabled={loading || (mode === 'public' && !keyword.trim())}>
              {loading ? <span className="spinner-border spinner-border-sm" /> : '搜索'}
            </button>
          </div>
        </div>
        <div className="segmented-control">
          <button className={mode === 'public' ? 'active' : ''} onClick={() => onModeChange('public')}>公开搜索</button>
          <button className={mode === 'local' ? 'active' : ''} onClick={() => onModeChange('local')}>本地库</button>
        </div>
        <div className="segmented-control compact">
          <button className={viewMode === 'list' ? 'active' : ''} onClick={() => onViewModeChange('list')}><List size={15} /> 列表</button>
          <button className={viewMode === 'grid' ? 'active' : ''} onClick={() => onViewModeChange('grid')}><Grid3X3 size={15} /> 海报</button>
        </div>
      </div>

      {!compact && (
        <div className="search-toolbar">
          {mode === 'public' && (
            <IconButton icon={Filter} className="btn-outline-secondary btn-sm" onClick={onToggleFilters}>
              筛选条件
            </IconButton>
          )}
          <IconButton icon={RefreshCcw} className="btn-outline-secondary btn-sm" onClick={onRefresh} disabled={(mode === 'public' && !keyword.trim()) || loading}>
            {refreshLabel}
          </IconButton>
          <IconButton icon={Settings2} className="btn-outline-secondary btn-sm" onClick={onToggleManagement}>
            管理操作
          </IconButton>
          {searchMeta && (
            <div className="search-stats">
              <span>{total} 条结果</span>
              <span>{searchMeta.elapsed_ms}ms</span>
              <span>{getSearchSourceLabel(searchMeta.source)}</span>
              {searchMeta.cached && <span>缓存</span>}
            </div>
          )}
        </div>
      )}

      {!compact && showFilters && mode === 'public' && (
        <div className="filter-panel">
          <div>
            <div className="filter-label">公开频道</div>
            <div className="chip-row">
              <button className={`chip ${selectedChannels.length === 0 ? 'active' : ''}`} onClick={onClearChannels}>全部</button>
              {channels.map(channel => (
                <button key={channel.id} className={`chip ${selectedChannels.includes(channel.url) ? 'active' : ''}`} onClick={() => onToggleChannel(channel.url)}>
                  {channel.url}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="filter-label">链接类型</div>
            <div className="chip-row">
              {CLOUD_TYPES.map(type => (
                <button key={type} className={`chip ${cloudTypes.includes(type) ? 'active' : ''}`} onClick={() => onToggleCloudType(type)}>
                  {type}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {!compact && showManagement && (
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

export default SearchCommandBar;
