import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { getApiErrorMessage } from '../api/errors';
import { getPosterWall } from '../api/search';
import {
  HOME_POSTER_REFRESH_DURATION_MS,
  HOME_POSTER_REFRESH_INTERVAL_MS,
} from '../config/app';
import { DEFAULT_POSTER_CATEGORY, getPosterApiCategory, getPosterProviderForCategory } from '../utils/media';

export function useHomePosterWall({ mode, runSearch, getLocalPage }) {
  const [posterWall, setPosterWall] = useState([]);
  const [posterWallError, setPosterWallError] = useState(null);
  const [posterCategory, setPosterCategory] = useState(DEFAULT_POSTER_CATEGORY);
  const [posterLoading, setPosterLoading] = useState(false);
  const [posterRefreshUntil, setPosterRefreshUntil] = useState(null);

  const fetchPosterWall = useCallback(async (category = posterCategory) => {
    setPosterLoading(true);
    setPosterWallError(null);
    try {
      const provider = getPosterProviderForCategory(category);
      const response = await getPosterWall(getPosterApiCategory(category), { provider });
      setPosterWall(response.data.items || []);
      if (response.data.available === false) {
        setPosterWallError(response.data.error || response.data.message || '海报墙暂不可用');
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, '获取海报墙失败'));
      setPosterWallError(getApiErrorMessage(error, '获取海报墙失败'));
    } finally {
      setPosterLoading(false);
    }
  }, [posterCategory]);

  useEffect(() => {
    fetchPosterWall().catch(() => {});
  }, [fetchPosterWall]);

  const startPosterRefresh = useCallback(() => {
    setPosterRefreshUntil(Date.now() + HOME_POSTER_REFRESH_DURATION_MS);
  }, []);

  useEffect(() => {
    if (!posterRefreshUntil) return undefined;
    if (Date.now() >= posterRefreshUntil) {
      setPosterRefreshUntil(null);
      return undefined;
    }

    const refreshPosterData = () => {
      fetchPosterWall().catch(() => {});
      if (mode === 'local') {
        runSearch({ forceRefresh: true, nextPage: getLocalPage(), silent: true });
      }
    };

    refreshPosterData();
    const intervalId = setInterval(() => {
      if (Date.now() >= posterRefreshUntil) {
        clearInterval(intervalId);
        setPosterRefreshUntil(null);
        return;
      }
      refreshPosterData();
    }, HOME_POSTER_REFRESH_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [fetchPosterWall, getLocalPage, mode, posterRefreshUntil, runSearch]);

  return {
    posterWall,
    posterWallError,
    posterCategory,
    posterLoading,
    fetchPosterWall,
    setPosterCategory,
    startPosterRefresh,
  };
}
