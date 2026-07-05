import React, { useMemo, useState } from 'react';
import { Archive, Copy, Database, Film } from 'lucide-react';

import MessageCard from '../MessageCard';
import { EmptyState, IconButton, LoadingState, MediaLibraryStatus } from '../ui';
import { formatDateTime, truncateText } from '../../utils/text';
import { getLibraryState, getPrimary115Link } from '../../utils/media';

const SORT_OPTIONS = [
  ['score', '综合排序'],
  ['latest', '最新发布'],
  ['quality', '质量优先'],
  ['confidence', '匹配优先'],
];

const QUALITY_RANK = {
  '4K': 70,
  'REMUX': 60,
  'BluRay': 50,
  'WEB-DL': 40,
  '1080p': 30,
  'HDR': 20,
  '720p': 10,
};

function getSourceKey(item) {
  if (Array.isArray(item.source_groups) && item.source_groups.length) return item.source_groups[0];
  if (item.source === 'pansou') return 'pansou';
  if (item.source === 'public_realtime' || item.source_group === 'public_channel') return 'public_channel';
  return item.source_group || item.source || item.source_label || item.channel_name || 'unknown';
}

function getSourceLabel(item) {
  if (item.source === 'pansou') return 'PanSou';
  if (item.source === 'public_realtime' || item.source_group === 'public_channel') return '自定义公开频道';
  return item.source_label || item.channel_name || item.source || '未知来源';
}

function getResultSourceText(item) {
  const labels = Array.isArray(item.source_labels) ? item.source_labels.filter(Boolean) : [];
  if (labels.length > 1) return labels.join(' / ');
  const groups = Array.isArray(item.source_groups) ? item.source_groups : [];
  if (groups.includes('pansou') && groups.includes('public_channel')) {
    return labels.length === 1 ? `${labels[0]} / 自定义公开频道` : 'PanSou / 自定义公开频道';
  }
  if (item.source === 'pansou') return item.source_label || 'PanSou';
  if (item.source === 'public_realtime' || item.source_group === 'public_channel') {
    return `自定义公开频道：${item.channel_name || item.source_label || '-'}`;
  }
  return item.source_label || item.channel_name || item.source || '未知来源';
}

function getQualityScore(item) {
  return (item.quality_tags || []).reduce((score, tag) => Math.max(score, QUALITY_RANK[tag] || 0), 0);
}

function getPublishTime(item) {
  const time = Date.parse(item.publish_date || '');
  return Number.isNaN(time) ? 0 : time;
}

function SearchResultsList({
  loading,
  results,
  viewMode,
  mode,
  keyword,
  sourceOptions: sourceOptionsOverride = null,
  sourceFilter: controlledSourceFilter,
  loadingLabel = '正在搜索...',
  onSourceFilterChange,
  onCopyText,
  onForwardLink,
  onOpenDetail,
  onSelectResult,
  selectedItem,
  onRetry,
}) {
  const [internalSourceFilter, setInternalSourceFilter] = useState('all');
  const [qualityFilter, setQualityFilter] = useState('all');
  const [sortMode, setSortMode] = useState('score');
  const sourceFilter = controlledSourceFilter ?? internalSourceFilter;
  const setSourceFilter = onSourceFilterChange ?? setInternalSourceFilter;

  const sourceOptions = useMemo(() => {
    if (sourceOptionsOverride) {
      const options = sourceOptionsOverride.map(item => {
        if (Array.isArray(item)) return item;
        const key = item.key || item.value || item.channel_name;
        const count = item.count ? ` (${item.count})` : '';
        return [key, `${item.label || item.channel_name || key}${count}`];
      }).filter(([key]) => key);
      if (controlledSourceFilter && controlledSourceFilter !== 'all' && !options.some(([key]) => key === controlledSourceFilter)) {
        options.push([controlledSourceFilter, controlledSourceFilter]);
      }
      return options;
    }
    const map = new Map();
    results.forEach(item => {
      const groups = Array.isArray(item.source_groups) && item.source_groups.length ? item.source_groups : [getSourceKey(item)];
      groups.forEach(key => {
        if (!map.has(key)) {
          map.set(key, key === 'pansou' ? 'PanSou' : (key === 'public_channel' ? '自定义公开频道' : getSourceLabel(item)));
        }
      });
    });
    return Array.from(map.entries());
  }, [controlledSourceFilter, results, sourceOptionsOverride]);

  const qualityOptions = useMemo(() => {
    const tags = new Set();
    results.forEach(item => (item.quality_tags || []).forEach(tag => tags.add(tag)));
    return Array.from(tags).sort((a, b) => (QUALITY_RANK[b] || 0) - (QUALITY_RANK[a] || 0) || a.localeCompare(b));
  }, [results]);

  const visibleResults = useMemo(() => {
    const filtered = results.filter(item => {
      if (!onSourceFilterChange && sourceFilter !== 'all') {
        const groups = Array.isArray(item.source_groups) && item.source_groups.length ? item.source_groups : [getSourceKey(item)];
        if (!groups.includes(sourceFilter)) return false;
      }
      if (qualityFilter !== 'all' && !(item.quality_tags || []).includes(qualityFilter)) return false;
      return true;
    });
    return [...filtered].sort((a, b) => {
      if (sortMode === 'latest') return getPublishTime(b) - getPublishTime(a);
      if (sortMode === 'quality') return getQualityScore(b) - getQualityScore(a) || (b.score || 0) - (a.score || 0);
      if (sortMode === 'confidence') return (b.confidence || 0) - (a.confidence || 0) || (b.score || 0) - (a.score || 0);
      return (b.score || 0) - (a.score || 0) || (b.confidence || 0) - (a.confidence || 0) || getPublishTime(b) - getPublishTime(a);
    });
  }, [onSourceFilterChange, qualityFilter, results, sortMode, sourceFilter]);

  if (loading) {
    return <LoadingState label={loadingLabel} />;
  }

  if (results.length === 0) {
    return (
      <EmptyState
        icon={mode === 'local' ? Database : Film}
        title={keyword.trim() ? '没有找到结果' : (mode === 'local' ? '本地库暂无消息' : '输入关键词开始搜索')}
        description={mode === 'local' ? '本地库会默认展示最近消息，也可以输入关键词筛选。' : '默认使用公开实时搜索，不需要 Telegram 账号登录。'}
      />
    );
  }

  const resultControls = (
    <div className="result-controls">
      <label>
        <span>来源</span>
        <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
          <option value="all">全部来源</option>
          {sourceOptions.map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </label>
      <label>
        <span>质量</span>
        <select value={qualityFilter} onChange={(event) => setQualityFilter(event.target.value)}>
          <option value="all">全部质量</option>
          {qualityOptions.map(tag => (
            <option key={tag} value={tag}>{tag}</option>
          ))}
        </select>
      </label>
      <label>
        <span>排序</span>
        <select value={sortMode} onChange={(event) => setSortMode(event.target.value)}>
          {SORT_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      <div className="result-controls-count">{visibleResults.length} / {results.length} 条</div>
    </div>
  );

  if (visibleResults.length === 0) {
    return (
      <>
        {resultControls}
        <EmptyState
          icon={Film}
          title="当前筛选无结果"
          description="调整来源、质量或排序条件后再查看。"
        />
      </>
    );
  }

  if (viewMode === 'grid') {
    return (
      <>
        {resultControls}
        <div className="media-grid">
          {visibleResults.map((item, index) => (
            <div key={item.id || `${item.channel_name}-${index}`}>
              <MessageCard message={item} onRetry={onRetry} onClick={() => onSelectResult ? onSelectResult(item) : onOpenDetail(item)} />
            </div>
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      {resultControls}
      <div className="compact-results">
        {visibleResults.map((item, index) => {
          const transferLink = getPrimary115Link(item);
          const copyLink = item.resource_url || transferLink;
          const transferableItem = transferLink ? { ...item, resource_url: transferLink } : item;
          const handleSelect = () => onSelectResult?.(item);
          const selected = selectedItem === item || (
            selectedItem
            && String(selectedItem.id || selectedItem.message_id || selectedItem.resource_url || selectedItem.title || '')
              === String(item.id || item.message_id || item.resource_url || item.title || '')
          );
          return (
            <article className={`compact-result-item ${selected ? 'selected' : ''}`.trim()} key={item.id || `${item.channel_name}-${index}`}>
              <div
                className="result-main result-main-clickable"
                role="button"
                tabIndex={0}
                onClick={handleSelect}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleSelect();
                  }
                }}
              >
                <div className="result-title-row">
                  <h3>{item.title || '无标题'}</h3>
                  <div className="type-tags">
                    {(item.quality_tags || []).slice(0, 4).map(tag => <span key={tag}>{tag}</span>)}
                    {(item.link_types || []).slice(0, 4).map(type => <span key={type}>{type}</span>)}
                  </div>
                </div>
                <div className="result-meta">
                  <span>{getResultSourceText(item)}</span>
                  <span>{formatDateTime(item.publish_date)}</span>
                  <span>{item.links?.length || 0} 个链接</span>
                  {item.score !== undefined && <span>排序 {Math.round(item.score)}</span>}
                  {item.confidence && <span>匹配 {Math.round(item.confidence * 100)}%</span>}
                  {getLibraryState(item) && <MediaLibraryStatus state={item.library_state || item.subscription_state} mediaType={item.tmdb_type} compact />}
                </div>
                {item.score_reason && <div className="result-score-reason">{item.score_reason}</div>}
                <p className="result-description">{item.description || item.raw_text || '暂无内容'}</p>
                {item.resource_url && <div className="result-url">{truncateText(item.resource_url, 88)}</div>}
              </div>
              <div className="result-actions">
                <IconButton icon={Copy} className="btn-success btn-sm" onClick={() => onCopyText(copyLink)} disabled={!copyLink}>复制链接</IconButton>
                <IconButton icon={Archive} className="btn-info btn-sm" onClick={() => onForwardLink(transferableItem)} disabled={!transferLink}>转存</IconButton>
                <button className="btn btn-outline-secondary btn-sm" onClick={() => onOpenDetail(item)}>详情</button>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}

export default SearchResultsList;
