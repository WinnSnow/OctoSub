import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Search, Star } from 'lucide-react';
import toast from 'react-hot-toast';

import SearchResultsList from '../components/home/SearchResultsList';
import MessageDetailModal from '../components/MessageDetailModal';
import TmdbDetailModal from '../components/TmdbDetailModal';
import { EmptyState, LoadingState, PageHeader } from '../components/ui';
import { getDoubanDetail, getTmdbDetail, searchMedia } from '../api/search';
import { transferResource } from '../api/transfers';
import { SEARCH_SCOPES, getSearchScopeConfig, normalizeSearchScope } from '../config/searchScopes';
import { useResourceSearchResults } from '../hooks/useResourceSearchResults';

const SEARCH_RESULT_SCOPES = SEARCH_SCOPES.filter(item => item.value !== 'library');

function normalizeMediaItems(payload) {
  const tmdb = Array.isArray(payload?.tmdb)
    ? payload.tmdb
    : (payload?.tmdb?.results || payload?.results || []);
  const douban = Array.isArray(payload?.douban)
    ? payload.douban
    : (payload?.douban?.results || payload?.douban?.items || []);
  return {
    tmdb: tmdb.map(item => ({ ...item, provider: item.provider || 'tmdb', source: item.source || 'tmdb' })),
    douban: douban.map(item => ({ ...item, provider: item.provider || 'douban', source: item.source || 'douban' })),
    doubanError: payload?.douban?.error || null,
  };
}

function mediaTitle(item) {
  return item?.title || item?.name || item?.original_title || item?.original_name || '未命名条目';
}

function mediaYear(item) {
  const year = item?.year || item?.release_year;
  if (year) return String(year);
  const date = item?.release_date || item?.first_air_date || item?.pubdate;
  return date ? String(date).slice(0, 4) : '';
}

function mediaType(item) {
  return item?.tmdb_type || item?.media_type || (item?.type === '电影' ? 'movie' : item?.type === '剧集' ? 'tv' : null);
}

function mediaTypeLabel(item) {
  const type = mediaType(item);
  if (type === 'movie') return '电影';
  if (type === 'tv') return '剧集';
  return item?.type || '影视';
}

function posterUrl(item) {
  return item?.poster_url || item?.image_url || item?.cover_url || item?.cover || '';
}

function overview(item) {
  return item?.overview || item?.summary || item?.description || '暂无简介';
}

function rating(item) {
  return item?.vote_average || item?.douban_rating || item?.rating || item?.score;
}

function buildContextFromParams(params, keyword) {
  const context = { keyword };
  const tmdbId = params.get('tmdb_id');
  const tmdbType = params.get('tmdb_type');
  const doubanId = params.get('douban_id');
  const year = params.get('year');
  if (tmdbId) context.tmdb_id = tmdbId;
  if (tmdbType) context.tmdb_type = tmdbType;
  if (doubanId) context.douban_id = doubanId;
  if (year) context.year = year;
  return Object.keys(context).length > 1 ? context : null;
}

function SearchStatusBar({ scope, keyword, onScopeChange }) {
  const config = getSearchScopeConfig(scope);
  return (
    <section className="search-status-bar">
      <div className="search-status-copy">
        <Search size={18} />
        <div>
          <div className="search-status-title">{config.label}{keyword ? `：${keyword}` : ''}</div>
          <div className="search-status-subtitle">
            {keyword ? '搜索结果由顶部全局搜索驱动' : '使用顶部全局搜索查找影视信息或资源'}
          </div>
        </div>
      </div>
      <div className="segmented-control">
        {SEARCH_RESULT_SCOPES.map(item => (
          <button
            type="button"
            key={item.value}
            className={scope === item.value ? 'active' : ''}
            onClick={() => onScopeChange(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function MediaResultCard({ item, onOpen }) {
  const itemRating = rating(item);
  const state = item.library_state || item.subscription_state;
  const isInLibrary = state?.status === 'completed';
  const sourceLabel = item.provider === 'douban' || item.source === 'douban' ? '豆瓣' : 'TMDB';
  const metaParts = [sourceLabel, mediaTypeLabel(item), mediaYear(item)].filter(Boolean);
  return (
    <article className="media-poster-result-card">
      <button type="button" className="media-poster-result-main" onClick={() => onOpen(item)}>
        <div className="media-poster-result-image">
          {posterUrl(item) ? <img src={posterUrl(item)} alt={mediaTitle(item)} loading="lazy" /> : <span>暂无海报</span>}
          {isInLibrary && (
            <span className="poster-corner-badge poster-corner-badge-left poster-corner-badge-success" aria-label="Jellyfin 已入库" title="Jellyfin 已入库">
              <CheckCircle2 size={16} />
            </span>
          )}
          {itemRating ? (
            <span className="poster-corner-badge poster-corner-badge-right poster-corner-badge-rating" aria-label={`评分 ${Number(itemRating).toFixed(1)}`}>
              <Star size={13} />
              {Number(itemRating).toFixed(1)}
            </span>
          ) : null}
        </div>
        <div className="media-poster-result-body">
          <span className="media-poster-result-title">{mediaTitle(item)}</span>
          <small>{metaParts.join(' · ')}</small>
        </div>
      </button>
    </article>
  );
}

function MediaSourceSection({ title, sourceLabel, items, onOpen, emptyLabel }) {
  return (
    <section className="media-source-section">
      <div className="media-source-header">
        <h2>{title}</h2>
        <span>{sourceLabel}</span>
      </div>
      {items.length > 0 ? (
        <div className="media-search-list">
          {items.map((item, index) => (
            <MediaResultCard
              key={`${item.provider || item.source}-${item.provider_id || item.tmdb_id || item.douban_id || item.id || index}`}
              item={item}
              onOpen={onOpen}
            />
          ))}
        </div>
      ) : (
        <div className="media-source-empty">{emptyLabel}</div>
      )}
    </section>
  );
}

function MediaSearchResults({ keyword, onSearchResources }) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState({ tmdb: [], douban: [], doubanError: null });
  const [detailState, setDetailState] = useState({
    show: false,
    loading: false,
    detail: null,
    error: '',
  });
  const requestIdRef = useRef(0);

  useEffect(() => {
    const trimmed = keyword.trim();
    if (!trimmed) {
      requestIdRef.current += 1;
      setItems({ tmdb: [], douban: [], doubanError: null });
      setLoading(false);
      return undefined;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    searchMedia(trimmed)
      .then(response => {
        if (requestId !== requestIdRef.current) return;
        setItems(normalizeMediaItems(response.data || {}));
      })
      .catch(() => {
        if (requestId !== requestIdRef.current) return;
        setItems({ tmdb: [], douban: [], doubanError: null });
        toast.error('影视信息搜索失败');
      })
      .finally(() => {
        if (requestId === requestIdRef.current) setLoading(false);
      });

    return undefined;
  }, [keyword]);

  const openDetail = async (item) => {
    setDetailState({ show: true, loading: true, detail: null, error: '' });
    try {
      const provider = item.provider || item.source;
      const type = mediaType(item) || 'movie';
      const response = provider === 'douban'
        ? await getDoubanDetail(item.douban_id || item.provider_id || item.id, type)
        : await getTmdbDetail(type, item.tmdb_id || item.id);
      setDetailState({ show: true, loading: false, detail: response.data, error: '' });
    } catch {
      setDetailState({ show: true, loading: false, detail: item, error: '详情加载失败，已展示搜索结果摘要。' });
    }
  };

  if (!keyword.trim()) {
    return (
      <EmptyState
        icon={Search}
        title="使用顶部全局搜索"
        description="查找影视信息，或切换为搜索资源直接查 PanSou 和本地库。"
      />
    );
  }

  if (loading) return <LoadingState label="正在搜索影视信息..." />;

  if (items.tmdb.length === 0 && items.douban.length === 0) {
    return (
      <EmptyState
        icon={Search}
        title="没有找到影视条目"
        description="可以切换到搜索资源，用关键词直接查 PanSou 和本地库。"
      />
    );
  }

  return (
    <div className="media-search-results">
      <MediaSourceSection
        title="TMDB"
        sourceLabel={`${items.tmdb.length} 条`}
        items={items.tmdb}
        onOpen={openDetail}
        emptyLabel="TMDB 暂无结果"
      />
      <MediaSourceSection
        title="豆瓣"
        sourceLabel={`${items.douban.length} 条`}
        items={items.douban}
        onOpen={openDetail}
        emptyLabel={items.doubanError ? `豆瓣搜索不可用：${items.doubanError}` : '豆瓣暂无结果'}
      />
      <TmdbDetailModal
        show={detailState.show}
        loading={detailState.loading}
        detail={detailState.detail}
        error={detailState.error}
        onClose={() => setDetailState({ show: false, loading: false, detail: null, error: '' })}
        onSearch={onSearchResources}
      />
    </div>
  );
}

function ResourceSection({ title, subtitle, children }) {
  return (
    <section className="resource-result-section">
      <div className="resource-result-header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function SearchPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [selectedMessage, setSelectedMessage] = useState(null);
  const {
    loading,
    onlineResults,
    localResults,
    onlineMeta,
    localMeta,
    onlineTotal,
    localTotal,
    runResourceSearch,
  } = useResourceSearchResults();
  const lastAppliedRef = useRef('');
  const scope = normalizeSearchScope(searchParams.get('scope'));
  const keyword = searchParams.get('q') || '';
  const contextKey = searchParams.toString();
  const context = useMemo(() => buildContextFromParams(searchParams, keyword), [contextKey, keyword, searchParams]);

  useEffect(() => {
    if (scope !== 'library') return;
    const params = new URLSearchParams();
    if (keyword) params.set('q', keyword);
    navigate(`/library${params.toString() ? `?${params.toString()}` : ''}`, { replace: true });
  }, [keyword, navigate, scope]);

  useEffect(() => {
    if (scope !== 'resources') return;
    const requestKey = `${scope}|${keyword}|${contextKey}`;
    if (lastAppliedRef.current === requestKey) return;
    lastAppliedRef.current = requestKey;
    runResourceSearch({ keyword, context });
  }, [context, contextKey, keyword, runResourceSearch, scope]);

  const updateScope = (nextScope) => {
    if (nextScope === 'library') {
      const params = new URLSearchParams();
      if (keyword) params.set('q', keyword);
      navigate(`/library${params.toString() ? `?${params.toString()}` : ''}`);
      return;
    }
    const params = new URLSearchParams();
    params.set('scope', nextScope);
    if (keyword) params.set('q', keyword);
    navigate(`/search?${params.toString()}`);
  };

  const searchResourcesForMedia = (item) => {
    const title = mediaTitle(item) || keyword;
    const params = new URLSearchParams({ scope: 'resources', q: title });
    const provider = item.provider || item.metadata_source || item.source;
    const type = mediaType(item);
    const tmdbId = item.tmdb_id || (provider !== 'douban' ? item.id : null);
    const doubanId = item.douban_id || item.provider_id || (provider === 'douban' ? item.id : null);
    const year = item.year || item.release_year;
    if (provider === 'douban' && doubanId) {
      params.set('douban_id', doubanId);
    } else if (tmdbId) {
      params.set('tmdb_id', tmdbId);
      if (type) params.set('tmdb_type', type);
    }
    if (year) params.set('year', String(year));
    navigate(`/search?${params.toString()}`);
  };

  const copyText = async (text) => {
    if (!text) return toast.error('没有可复制的链接');
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      toast.success('链接已复制');
    } catch {
      toast.error('复制失败');
    }
  };

  const forwardLink = async (itemOrLink) => {
    const link = typeof itemOrLink === 'string' ? itemOrLink : itemOrLink?.resource_url;
    const title = typeof itemOrLink === 'string' ? null : itemOrLink?.title;
    if (!link) return toast.error('没有可转存的链接');
    const toastId = toast.loading('正在发送转存请求...');
    try {
      await transferResource({ url: link, title });
      toast.success('转存请求已发送', { id: toastId });
    } catch {
      toast.error('转存失败', { id: toastId });
    }
  };

  const renderResourceResults = () => {
    if (!keyword.trim()) {
      return (
        <EmptyState
          icon={Search}
          title="输入关键词搜索资源"
          description="使用顶部全局搜索直接查找 PanSou 和本地库资源。"
        />
      );
    }

    return (
      <div className="resource-result-layout">
        <ResourceSection
          title="在线资源"
          subtitle={onlineMeta ? `${onlineTotal} 条结果` : 'PanSou 与公开资源搜索'}
        >
          {onlineMeta?.failed_channels?.length > 0 && (
            <div className="alert alert-warning py-2">
              部分频道搜索失败：{onlineMeta.failed_channels.map(item => item.channel).join(', ')}
            </div>
          )}
          <SearchResultsList
            loading={loading}
            loadingLabel="正在搜索在线资源..."
            results={onlineResults}
            viewMode="list"
            mode="resources"
            keyword={keyword}
            onCopyText={copyText}
            onForwardLink={forwardLink}
            onOpenDetail={setSelectedMessage}
            onSelectResult={setSelectedMessage}
            onRetry={() => runResourceSearch({ keyword, context, forceRefresh: true })}
          />
        </ResourceSection>

        <ResourceSection
          title="本地库"
          subtitle={localMeta ? `${localTotal} 条结果` : '本地已抓取资源'}
        >
          <SearchResultsList
            loading={loading}
            loadingLabel="正在搜索本地库..."
            results={localResults}
            viewMode="list"
            mode="local"
            keyword={keyword}
            onCopyText={copyText}
            onForwardLink={forwardLink}
            onOpenDetail={setSelectedMessage}
            onSelectResult={setSelectedMessage}
            onRetry={() => runResourceSearch({ keyword, context, forceRefresh: true })}
          />
        </ResourceSection>
      </div>
    );
  };

  if (scope === 'library') return null;

  return (
    <div className="search-workspace fade-in">
      <PageHeader
        eyebrow="Global Search"
        title="全局搜索"
        description="搜索页只展示全局搜索结果：先找影视信息，或直接搜索资源。"
      />

      <SearchStatusBar scope={scope} keyword={keyword} onScopeChange={updateScope} />

      {scope === 'media' && <MediaSearchResults keyword={keyword} onSearchResources={searchResourcesForMedia} />}
      {scope === 'resources' && renderResourceResults()}

      <MessageDetailModal show={Boolean(selectedMessage)} onClose={() => setSelectedMessage(null)} message={selectedMessage} />
    </div>
  );
}

export default SearchPage;
