import { useCallback } from 'react';

import { getMessages } from '../api/messages';
import { buildLocalSearchParams, createLocalSearchState } from '../utils/homeSearchState';

export function useLocalSearchFlow() {
  const searchLocal = useCallback(async ({
    keyword,
    requestedPage,
    localChannels = [],
    startedAt,
  }) => {
    const params = buildLocalSearchParams({
      keyword,
      page: requestedPage,
      localChannels,
    });
    const response = await getMessages(params);
    return createLocalSearchState({
      data: response.data,
      requestedPage,
      startedAt,
      keyword,
      localChannels,
    });
  }, []);

  return { searchLocal };
}
