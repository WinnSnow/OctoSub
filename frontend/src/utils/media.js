export const CLOUD_TYPES = ['115', 'quark', 'baidu', 'aliyun', 'magnet', 'ed2k', 'others'];
export const DEFAULT_CLOUD_TYPES = ['115'];

export const POSTER_CATEGORIES = [
  { value: 'douban_movie_hot', label: '豆瓣电影' },
  { value: 'douban_movie_showing', label: '热映' },
  { value: 'douban_movie_latest', label: '新片' },
  { value: 'douban_tv_hot', label: '豆瓣剧集' },
  { value: 'douban_tv_latest', label: '新剧' },
  { value: 'douban_tv_weekly_chinese', label: '华语周榜' },
  { value: 'douban_tv_weekly_global', label: '全球周榜' },
  { value: 'douban_tv_animation', label: '动画' },
  { value: 'trending', label: 'TMDB趋势' },
  { value: 'now_playing', label: '上映' },
  { value: 'on_the_air', label: '播出' },
  { value: 'douban_movie_top250', label: '豆瓣 Top250' },
  { value: 'subscriptions', label: '订阅' },
];

export const DEFAULT_POSTER_CATEGORY = POSTER_CATEGORIES[0].value;

export function getPosterProviderForCategory(category) {
  return String(category || '').startsWith('douban_') ? 'douban' : 'tmdb';
}

export function getPosterApiCategory(category) {
  const value = String(category || '');
  return value.startsWith('douban_') ? value.replace(/^douban_/, '') : value;
}

const SEARCH_SOURCE_LABELS = {
  combined: '在线聚合',
  pansou: 'PanSou',
  public_realtime: '公开频道',
  local_library: '本地库',
};

const MEDIA_TYPE_LABELS = {
  tv: '剧集',
  movie: '电影',
};

export function getSearchSourceLabel(source) {
  return SEARCH_SOURCE_LABELS[source] || source || '未知来源';
}

export function getMediaTypeLabel(mediaType) {
  return MEDIA_TYPE_LABELS[mediaType] || '未知';
}

export function getMediaTypeBadgeClass(mediaType) {
  return mediaType === 'tv' ? 'bg-primary' : 'bg-success';
}

export function is115Link(url) {
  return /^https?:\/\/(?:www\.)?(?:115\.com|115cdn\.com)\//i.test((url || '').trim());
}

export function getPrimary115Link(item) {
  if (is115Link(item?.resource_url)) return item.resource_url;
  const link = (item?.links || []).find(candidate => (
    candidate?.type === '115' || is115Link(candidate?.url)
  ));
  return link?.url || '';
}

export function getPosterStateLabel(item) {
  const state = item.library_state || item.subscription_state;
  if (!state) return null;
  if (state.status === 'completed') return state.label || '已入库';
  if (state.status === 'partial') return state.label || '部分入库';
  if (state.status === 'missing') return null;
  return state.progress_total > 0 ? `${state.progress_current}/${state.progress_total}` : (state.label || '订阅中');
}

export function getLibraryState(item) {
  const state = item.library_state || item.subscription_state;
  if (!state) return null;
  if (state.status === 'completed') return state.label || '已入库';
  if (state.status === 'partial') return state.label || '部分入库';
  if (state.status === 'missing') return null;
  return state.label || '订阅中';
}

export function formatLibraryStateText(state, mediaType = null) {
  if (!state) return null;
  const current = Number(state.progress_current || 0);
  const total = Number(state.progress_total || 0);
  const missing = total > 0 ? Math.max(total - current, 0) : 0;
  const isTv = mediaType === 'tv' || state.media_type === 'tv';

  if (state.status === 'completed') {
    if (isTv && total > 1) {
      return {
        title: `已完整入库 ${current}/${total}`,
        detail: state.completed_at ? `Jellyfin 已完成，完成时间 ${state.completed_at}` : 'Jellyfin 已确认所有已知集数',
        tone: 'success',
      };
    }
    return {
      title: state.label || '已入库',
      detail: 'Jellyfin 媒体库已有这个作品',
      tone: 'success',
    };
  }

  if (state.status === 'missing') return null;

  if (state.status === 'paused') {
    return {
      title: '已暂停订阅',
      detail: '不会参与定时检查，也不会自动搜索资源',
      tone: 'muted',
    };
  }

  if (isTv && total > 0) {
    return {
      title: missing > 0 ? `已入库 ${current}/${total}，缺失 ${missing} 集` : `已入库 ${current}/${total}`,
      detail: missing > 0 ? '自动检查只追下一集，历史缺失需手动处理' : '正在等待新的集数信息',
      tone: missing > 0 ? 'warning' : 'success',
    };
  }

  return {
    title: state.label || '订阅中',
    detail: '还未在 Jellyfin 中确认完整入库',
    tone: 'warning',
  };
}
