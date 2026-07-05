import { useCallback } from 'react';

import { searchResources } from '../api/search';
import { buildPublicSearchParams, createPublicSearchState } from '../utils/homeSearchState';

export function usePublicSearchFlow({ cloudTypes, searchContext }) {
  const searchPublic = useCallback(async ({
    keyword,
    forceRefresh = false,
    overrideContext = null,
    selectedChannels = [],
  }) => {
    const params = buildPublicSearchParams({
      keyword,
      cloudTypes,
      forceRefresh,
      searchContext: overrideContext || searchContext,
      selectedChannels,
    });
    const response = await searchResources(params);
    return createPublicSearchState(response.data);
  }, [cloudTypes, searchContext]);

  return { searchPublic };
}
