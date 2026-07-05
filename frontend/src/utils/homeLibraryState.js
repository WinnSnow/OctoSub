export function buildLibraryStateKey(item, index) {
  const primaryId = item.tmdb_id
    ? `tmdb:${item.tmdb_type || ''}:${item.tmdb_id}`
    : (item.id ? `id:${item.source || item.channel_name || ''}:${item.id}` : '');
  return [
    primaryId,
    item.channel_name || '',
    item.message_id || '',
    item.resource_url || '',
    item.title || '',
    index,
  ].join('|');
}

export function attachLibraryStateKeys(items) {
  return items.map((item, index) => ({
    ...item,
    library_state_key: item.library_state_key || buildLibraryStateKey(item, index),
  }));
}

export function buildLibraryStatePayload(items) {
  return items
    .filter(item => item?.library_state_key)
    .map(item => ({
      key: item.library_state_key,
      title: item.title,
      raw_text: item.raw_text,
      description: item.description,
      tmdb_id: item.tmdb_id,
      tmdb_type: item.tmdb_type,
      media_type: item.media_type,
      year: item.year,
      season: item.season,
      episode: item.episode,
      library_check_title: item.library_check_title,
      subscription_keyword: item.subscription_keyword,
      search_keyword: item.search_keyword,
      subscription_state: item.subscription_state,
    }));
}

export function mergeLibraryStates(items, statesByKey) {
  return items.map(item => {
    const state = statesByKey.get(item.library_state_key);
    if (!state) return item;
    if (!state.library_state && !state.library_status) return item;
    return {
      ...item,
      library_state: state.library_state || item.library_state,
      library_status: state.library_status || item.library_status,
    };
  });
}
