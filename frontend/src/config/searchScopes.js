export const SEARCH_SCOPES = [
  {
    value: 'media',
    label: '影视信息',
    placeholder: '搜索电影、剧集、综艺、动画',
  },
  {
    value: 'resources',
    label: '搜索资源',
    placeholder: '搜索可转存资源',
  },
  {
    value: 'library',
    label: '资源库',
    placeholder: '搜索资源库内容',
  },
];

export const DEFAULT_SEARCH_SCOPE = 'media';
export const SEARCH_SCOPE_STORAGE_KEY = 'octosub.globalSearchScope';

export function normalizeSearchScope(scope) {
  return SEARCH_SCOPES.some(item => item.value === scope) ? scope : DEFAULT_SEARCH_SCOPE;
}

export function getSearchScopeConfig(scope) {
  return SEARCH_SCOPES.find(item => item.value === normalizeSearchScope(scope)) || SEARCH_SCOPES[0];
}
