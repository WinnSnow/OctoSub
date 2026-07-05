import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';

import { retryMissingForChannel, scrape } from '../api/channels';
import { getApiErrorMessage } from '../api/errors';
import { clearMessages as clearMessagesApi, matchPosters as matchPostersApi } from '../api/messages';
import { getLibraryStates } from '../api/search';
import { transferResource } from '../api/transfers';
import {
  HOME_LOCAL_PAGE_SIZE,
  HOME_LOCAL_SEARCH_DEBOUNCE_MS,
} from '../config/app';
import { useHomeChannels } from './useHomeChannels';
import { useHomePosterWall } from './useHomePosterWall';
import { useHomeTaskController } from './useHomeTaskController';
import { useLocalSearchFlow } from './useLocalSearchFlow';
import { usePublicSearchFlow } from './usePublicSearchFlow';
import { buildLibraryStatePayload, mergeLibraryStates } from '../utils/homeLibraryState';
import { DEFAULT_CLOUD_TYPES } from '../utils/media';

function scrollHomeContentToTop() {
  if (typeof document === 'undefined') return;
  const scrollTarget = document.querySelector('.main-content') || document.scrollingElement || document.documentElement;
  if (scrollTarget?.scrollTo) {
    scrollTarget.scrollTo({ top: 0, behavior: 'smooth' });
  }
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

export function useHomeSearch() {
  const [keyword, setKeyword] = useState('');
  const [searchContext, setSearchContext] = useState(null);
  const [isComposing, setIsComposing] = useState(false);
  const [mode, setMode] = useState('public');
  const [viewMode, setViewMode] = useState('list');
  const [cloudTypes, setCloudTypes] = useState(DEFAULT_CLOUD_TYPES);
  const [results, setResults] = useState([]);
  const [localSources, setLocalSources] = useState([]);
  const [searchMeta, setSearchMeta] = useState(null);
  const [modeSnapshots, setModeSnapshots] = useState({});
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showManagement, setShowManagement] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const searchRequestIdRef = useRef(0);
  const loadingRequestIdRef = useRef(0);
  const foregroundRequestIdRef = useRef(0);
  const localPageRef = useRef(1);
  const scrollAfterLocalPageLoadRef = useRef(false);
  const libraryStateRequestIdRef = useRef(0);
  const getCurrentLocalPage = useCallback(() => localPageRef.current, []);

  const localPagination = useMemo(() => {
    const pageSize = searchMeta?.limit || HOME_LOCAL_PAGE_SIZE;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    return {
      page,
      total,
      pageSize,
      totalPages,
      hasPrevious: page > 1,
      hasNext: page < totalPages,
      visible: mode === 'local' && totalPages > 1,
    };
  }, [mode, page, searchMeta, total]);

  const requestLibraryStates = useCallback((items, snapshotMode) => {
    const stateRequestId = libraryStateRequestIdRef.current + 1;
    libraryStateRequestIdRef.current = stateRequestId;
    const payloadItems = buildLibraryStatePayload(items);
    if (payloadItems.length === 0) return;

    getLibraryStates({ items: payloadItems })
      .then(response => {
        if (stateRequestId !== libraryStateRequestIdRef.current) return;
        const statesByKey = new Map((response.data.states || []).map(state => [state.key, state]));
        if (statesByKey.size === 0) return;
        setResults(prev => mergeLibraryStates(prev, statesByKey));
        setModeSnapshots(prev => {
          const snapshot = prev[snapshotMode];
          if (!snapshot) return prev;
          return {
            ...prev,
            [snapshotMode]: {
              ...snapshot,
              results: mergeLibraryStates(snapshot.results || [], statesByKey),
            },
          };
        });
      })
      .catch(() => {});
  }, []);

  const runSearchRef = useRef(null);
  const runSearchProxy = useCallback((options) => runSearchRef.current?.(options), []);
  const {
    channels,
    selectedChannels,
    localSourceFilter,
    setSelectedChannels,
    setLocalSourceFilter,
    toggleChannel,
    selectLocalSource,
  } = useHomeChannels({ mode, runSearch: runSearchProxy });
  const {
    posterWall,
    posterWallError,
    posterCategory,
    posterLoading,
    fetchPosterWall,
    setPosterCategory,
    startPosterRefresh,
  } = useHomePosterWall({
    mode,
    runSearch: runSearchProxy,
    getLocalPage: getCurrentLocalPage,
  });
  const {
    activeTask,
    scraping,
    cancellingTaskId,
    trackTask,
    startTask,
    cancelActiveTask,
  } = useHomeTaskController({
    mode,
    page,
    runSearch: runSearchProxy,
    fetchPosterWall,
    startPosterRefresh,
  });
  const { searchPublic } = usePublicSearchFlow({ cloudTypes, searchContext });
  const { searchLocal } = useLocalSearchFlow();

  const runSearch = useCallback(async ({
    forceRefresh = false,
    nextPage = 1,
    overrideKeyword = null,
    overrideContext = null,
    overrideSelectedChannels = null,
    overrideLocalSourceFilter = null,
    silent = false,
  } = {}) => {
    const trimmed = (overrideKeyword ?? keyword).trim();
    const activeSelectedChannels = overrideSelectedChannels ?? selectedChannels;
    const activeLocalSourceFilter = overrideLocalSourceFilter ?? localSourceFilter;
    const activeLocalChannels = activeLocalSourceFilter && activeLocalSourceFilter !== 'all'
      ? [activeLocalSourceFilter]
      : [];
    if (mode === 'public' && !trimmed) {
      searchRequestIdRef.current += 1;
      foregroundRequestIdRef.current = searchRequestIdRef.current;
      libraryStateRequestIdRef.current += 1;
      setResults([]);
      setSearchMeta(null);
      setTotal(0);
      return;
    }

    const requestId = searchRequestIdRef.current + 1;
    searchRequestIdRef.current = requestId;
    if (!silent) {
      foregroundRequestIdRef.current = requestId;
      libraryStateRequestIdRef.current += 1;
    }
    if (!silent) {
      loadingRequestIdRef.current = requestId;
      setLoading(true);
    }
    const started = performance.now();
    try {
      if (mode === 'public') {
        const { results: nextResults, total: nextTotal, searchMeta: nextMeta } = await searchPublic({
          keyword: trimmed,
          forceRefresh,
          overrideContext,
          selectedChannels: activeSelectedChannels,
        });
        if (requestId !== foregroundRequestIdRef.current) return;
        setResults(nextResults);
        setTotal(nextTotal);
        setSearchMeta(nextMeta);
        setModeSnapshots(prev => ({
          ...prev,
          public: {
            results: nextResults,
            total: nextTotal,
            page: 1,
            searchMeta: nextMeta,
          },
        }));
        requestLibraryStates(nextResults, 'public');
      } else {
        const requestedPage = Math.max(1, nextPage);
        if (!silent) {
          localPageRef.current = requestedPage;
        }
        const {
          results: nextResults,
          total: nextTotal,
          localSources: nextLocalSources,
          page: nextPageValue,
          searchMeta: nextMeta,
        } = await searchLocal({
          keyword: trimmed,
          requestedPage,
          localChannels: activeLocalChannels,
          startedAt: started,
        });
        if (silent) {
          if (requestedPage !== localPageRef.current || requestId < foregroundRequestIdRef.current) return;
        } else if (requestId !== foregroundRequestIdRef.current) {
          return;
        }
        localPageRef.current = nextPageValue;
        setResults(nextResults);
        setLocalSources(nextLocalSources);
        setTotal(nextTotal);
        setPage(nextPageValue);
        setSearchMeta(nextMeta);
        setModeSnapshots(prev => ({
          ...prev,
          local: {
            results: nextResults,
            localSources: nextLocalSources,
            total: nextTotal,
            page: nextPageValue,
            searchMeta: nextMeta,
          },
        }));
        if (!silent && scrollAfterLocalPageLoadRef.current) {
          scrollAfterLocalPageLoadRef.current = false;
          window.requestAnimationFrame(scrollHomeContentToTop);
        }
        requestLibraryStates(nextResults, 'local');
      }
    } catch (error) {
      if (!silent && requestId === foregroundRequestIdRef.current) toast.error(getApiErrorMessage(error, '搜索失败'));
    } finally {
      if (!silent && loadingRequestIdRef.current === requestId) setLoading(false);
    }
  }, [keyword, localSourceFilter, mode, requestLibraryStates, searchLocal, searchPublic, selectedChannels]);

  useEffect(() => {
    runSearchRef.current = runSearch;
  }, [runSearch]);

  const changeMode = useCallback((nextMode) => {
    searchRequestIdRef.current += 1;
    libraryStateRequestIdRef.current += 1;
    loadingRequestIdRef.current = 0;
    setMode(nextMode);
    setLoading(false);
    const snapshot = modeSnapshots[nextMode];
    if (!snapshot) {
      setResults([]);
      setTotal(0);
      setPage(1);
      localPageRef.current = 1;
      setSearchMeta(null);
      return;
    }
    setResults(snapshot.results || []);
    setLocalSources(snapshot.localSources || []);
    setTotal(snapshot.total || 0);
    setPage(snapshot.page || 1);
    localPageRef.current = snapshot.page || 1;
    setSearchMeta(snapshot.searchMeta || null);
  }, [modeSnapshots]);

  const searchPoster = (item) => {
    const nextKeyword = (item.title || item.name || item.search_keyword || '').trim();
    const nextContext = {
      keyword: nextKeyword,
      tmdb_id: item.tmdb_id || null,
      tmdb_type: item.tmdb_type || null,
      douban_id: item.douban_id || null,
      douban_url: item.douban_url || null,
      douban_rating: item.douban_rating || null,
      year: item.year || null,
    };
    setSearchContext(nextContext);
    setKeyword(nextKeyword);
    setMode('public');
    setViewMode('list');
    runSearch({ forceRefresh: true, nextPage: 1, overrideKeyword: nextKeyword, overrideContext: nextContext });
  };

  useEffect(() => {
    if (mode !== 'local' || isComposing) return undefined;
    const timer = setTimeout(() => {
      runSearch({ nextPage: 1 });
    }, HOME_LOCAL_SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [isComposing, keyword, mode, localSourceFilter, runSearch]);

  const toggleCloudType = (type) => {
    setCloudTypes(prev => prev.includes(type) ? prev.filter(item => item !== type) : [...prev, type]);
  };

  const goToLocalPage = useCallback((targetPage) => {
    const boundedPage = Math.max(1, Math.min(targetPage, localPagination.totalPages));
    scrollAfterLocalPageLoadRef.current = true;
    return runSearch({ nextPage: boundedPage });
  }, [localPagination.totalPages, runSearch]);

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
    } catch (error) {
      toast.error('复制失败');
    }
  };

  const forwardLink = async (itemOrLink) => {
    const link = typeof itemOrLink === 'string' ? itemOrLink : itemOrLink?.resource_url;
    const title = typeof itemOrLink === 'string' ? null : itemOrLink?.title;
    if (!link) return toast.error('没有可转存的链接');
    const toastId = toast.loading('正在发送转存请求...');
    try {
      const response = await transferResource({ url: link, title });
      if (response.data?.task_id) {
        trackTask({
          task_id: response.data.task_id,
          type: 'transfer',
          title: title || '资源转存',
          total: 0,
          current: 0,
          status: response.data.status || 'running',
          message: response.data.message || '转存任务已启动',
        });
      }
      toast.success('转存请求已发送', { id: toastId });
    } catch (error) {
      toast.error(getApiErrorMessage(error, '转存失败'), { id: toastId });
    }
  };

  const handleScrapeAll = () => startTask(() => scrape(), { type: 'fetch', title: '频道抓取' });
  const handleRefreshChannel = (channelName) => startTask(
    () => scrape({ channel_name: channelName }),
    { type: 'fetch', title: `频道抓取：${channelName}` },
  );
  const handleRetryMissing = (channelName) => startTask(() => retryMissingForChannel(channelName));

  const clearMessages = async (channelName = null) => {
    const message = channelName ? `确定清空频道 ${channelName} 的本地消息吗？` : '确定清空所有本地消息吗？';
    if (!window.confirm(message)) return;
    try {
      await clearMessagesApi(channelName ? { channel_name: channelName } : undefined);
      toast.success('已清空');
      runSearch({ forceRefresh: true, nextPage: 1 });
    } catch (error) {
      toast.error('清空失败');
    }
  };

  const matchPosters = async () => {
    const toastId = toast.loading('正在启动海报匹配...');
    try {
      const response = await matchPostersApi();
      if (response.data?.task_id) {
        trackTask({
          task_id: response.data.task_id,
          type: 'poster_match',
          title: '批量海报匹配',
          total: 0,
          current: 0,
          status: response.data.status || 'running',
          message: response.data.message || '海报匹配已启动',
        });
      }
      toast.success(response.data.message || '海报匹配已启动', { id: toastId });
      startPosterRefresh();
    } catch (error) {
      toast.error('海报匹配启动失败', { id: toastId });
    }
  };

  const openDetail = (item) => {
    setSelectedMessage(item);
    setShowModal(true);
  };

  return {
    channels,
    localSources,
    selectedChannels,
    localSourceFilter,
    keyword,
    searchContext,
    isComposing,
    mode,
    viewMode,
    cloudTypes,
    results,
    posterWall,
    posterWallError,
    posterCategory,
    posterLoading,
    searchMeta,
    loading,
    showFilters,
    showManagement,
    scraping,
    activeTask,
    cancellingTaskId,
    selectedMessage,
    showModal,
    page,
    total,
    localPagination,
    setKeyword,
    setSearchContext,
    setIsComposing,
    setMode: changeMode,
    setViewMode,
    setLocalSourceFilter,
    setPosterCategory,
    setShowFilters,
    setShowManagement,
    setShowModal,
    setSelectedChannels,
    fetchPosterWall,
    runSearch,
    goToLocalPage,
    searchPoster,
    toggleCloudType,
    toggleChannel,
    selectLocalSource,
    copyText,
    forwardLink,
    handleScrapeAll,
    handleRefreshChannel,
    handleRetryMissing,
    clearMessages,
    matchPosters,
    cancelActiveTask,
    openDetail,
  };
}
