import { useCallback, useRef, useState } from 'react';
import toast from 'react-hot-toast';

import { getMessages } from '../api/messages';
import { getApiErrorMessage } from '../api/errors';
import { getLibraryStates, searchResources } from '../api/search';
import { HOME_LOCAL_PAGE_SIZE } from '../config/app';
import { DEFAULT_CLOUD_TYPES } from '../utils/media';
import { buildLibraryStatePayload, mergeLibraryStates } from '../utils/homeLibraryState';
import {
  buildLocalSearchParams,
  buildPublicSearchParams,
  createLocalSearchState,
  createPublicSearchState,
} from '../utils/homeSearchState';

export function useResourceSearchResults() {
  const [onlineResults, setOnlineResults] = useState([]);
  const [localResults, setLocalResults] = useState([]);
  const [onlineMeta, setOnlineMeta] = useState(null);
  const [localMeta, setLocalMeta] = useState(null);
  const [onlineTotal, setOnlineTotal] = useState(0);
  const [localTotal, setLocalTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const requestIdRef = useRef(0);

  const annotateLibraryStates = useCallback(async (items, apply) => {
    const payloadItems = buildLibraryStatePayload(items);
    if (payloadItems.length === 0) return;
    try {
      const response = await getLibraryStates({ items: payloadItems });
      const statesByKey = new Map((response.data.states || []).map(state => [state.key, state]));
      if (statesByKey.size > 0) apply(statesByKey);
    } catch {
      // Library state is auxiliary; search results should remain visible.
    }
  }, []);

  const runResourceSearch = useCallback(async ({ keyword, context = null, forceRefresh = false } = {}) => {
    const trimmed = (keyword || '').trim();
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    if (!trimmed) {
      setOnlineResults([]);
      setLocalResults([]);
      setOnlineMeta(null);
      setLocalMeta(null);
      setOnlineTotal(0);
      setLocalTotal(0);
      setLoading(false);
      return;
    }

    setLoading(true);
    const startedAt = performance.now();
    try {
      const [onlineResponse, localResponse] = await Promise.all([
        searchResources(buildPublicSearchParams({
          keyword: trimmed,
          cloudTypes: DEFAULT_CLOUD_TYPES,
          forceRefresh,
          searchContext: context,
        })),
        getMessages(buildLocalSearchParams({
          keyword: trimmed,
          page: 1,
          localChannels: [],
        })),
      ]);
      if (requestId !== requestIdRef.current) return;

      const onlineState = createPublicSearchState(onlineResponse.data);
      const localState = createLocalSearchState({
        data: localResponse.data,
        requestedPage: 1,
        startedAt,
        keyword: trimmed,
        localChannels: [],
      });

      setOnlineResults(onlineState.results);
      setOnlineMeta(onlineState.searchMeta);
      setOnlineTotal(onlineState.total);
      setLocalResults(localState.results);
      setLocalMeta({
        ...localState.searchMeta,
        limit: localResponse.data?.limit || HOME_LOCAL_PAGE_SIZE,
      });
      setLocalTotal(localState.total);

      annotateLibraryStates(onlineState.results, statesByKey => {
        if (requestId === requestIdRef.current) {
          setOnlineResults(prev => mergeLibraryStates(prev, statesByKey));
        }
      });
      annotateLibraryStates(localState.results, statesByKey => {
        if (requestId === requestIdRef.current) {
          setLocalResults(prev => mergeLibraryStates(prev, statesByKey));
        }
      });
    } catch (error) {
      if (requestId === requestIdRef.current) {
        toast.error(getApiErrorMessage(error, '搜索资源失败'));
      }
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [annotateLibraryStates]);

  return {
    loading,
    onlineResults,
    localResults,
    onlineMeta,
    localMeta,
    onlineTotal,
    localTotal,
    runResourceSearch,
  };
}
