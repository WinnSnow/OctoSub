import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Film, Info, RefreshCcw, Sparkles, Star } from 'lucide-react';

import { getApiErrorMessage } from '../api/errors';
import { getDoubanDetail, getPosterWall, getTmdbDetail } from '../api/search';
import TmdbDetailModal from '../components/TmdbDetailModal';
import { EmptyState, IconButton, LoadingState, PageHeader, Panel, StatusBadge } from '../components/ui';
import { getMediaTypeLabel } from '../utils/media';

const RECOMMENDATION_PROVIDERS = [
  { value: 'douban', label: '豆瓣', enabled: true },
  { value: 'tmdb', label: 'TMDB', enabled: true },
];

const DOUBAN_CATEGORY_OPTIONS = [
  { value: 'movie_hot', label: '热门电影', mediaType: 'movie' },
  { value: 'movie_showing', label: '正在热映', mediaType: 'movie' },
  { value: 'movie_latest', label: '最新电影', mediaType: 'movie' },
  { value: 'movie_top250', label: 'Top250', mediaType: 'movie' },
  { value: 'tv_hot', label: '热门剧集', mediaType: 'tv' },
  { value: 'tv_latest', label: '最新剧集', mediaType: 'tv' },
  { value: 'tv_weekly_chinese', label: '华语周榜', mediaType: 'tv' },
  { value: 'tv_weekly_global', label: '全球周榜', mediaType: 'tv' },
  { value: 'tv_animation', label: '动画', mediaType: 'tv' },
  { value: 'tv_variety', label: '综艺', mediaType: 'tv' },
];

const TMDB_CATEGORY_OPTIONS = [
  { value: 'trending_all', label: '趋势', category: 'trending', mediaType: 'all' },
  { value: 'popular_movie', label: '热门电影', category: 'popular', mediaType: 'movie' },
  { value: 'popular_tv', label: '热门剧集', category: 'popular', mediaType: 'tv' },
  { value: 'now_playing', label: '正在上映', category: 'now_playing', mediaType: 'movie' },
  { value: 'on_the_air', label: '正在播出', category: 'on_the_air', mediaType: 'tv' },
];

const PROVIDER_LABELS = {
  tmdb: 'TMDB',
  douban: '豆瓣',
  local: '本地',
};

function getProviderLabel(provider) {
  return PROVIDER_LABELS[provider] || provider || '推荐';
}

function buildSearchUrl(item) {
  const keyword = (item.title || item.name || item.search_keyword || '').trim();
  const params = new URLSearchParams();
  if (keyword) params.set('q', keyword);
  if (item.tmdb_id) params.set('tmdb_id', item.tmdb_id);
  if (item.tmdb_type) params.set('tmdb_type', item.tmdb_type);
  if (item.douban_id) params.set('douban_id', item.douban_id);
  if (item.year) params.set('year', item.year);
  return `/search?${params.toString()}`;
}

function RecommendationCard({ item, onOpenDetail }) {
  const state = item.library_state || item.subscription_state;
  const isInLibrary = state?.status === 'completed';
  const mediaType = item.tmdb_type || item.media_type;
  const rating = item.vote_average || item.douban_rating;
  const posterStyle = item.poster_url ? { '--media-poster-bg': `url("${item.poster_url}")` } : undefined;
  return (
    <article className="recommendation-card" style={posterStyle}>
      <button type="button" className="recommendation-poster" onClick={() => onOpenDetail(item)} aria-label={item.title}>
        {item.poster_url ? <img src={item.poster_url} alt={item.title} loading="lazy" /> : <Film size={28} />}
        {isInLibrary && (
          <span className="poster-corner-badge poster-corner-badge-left poster-corner-badge-success" aria-label="Jellyfin 已入库" title="Jellyfin 已入库">
            <CheckCircle2 size={16} />
          </span>
        )}
        {rating ? (
          <span className="poster-corner-badge poster-corner-badge-right poster-corner-badge-rating" aria-label={`评分 ${Number(rating).toFixed(1)}`}>
            <Star size={13} />
            {Number(rating).toFixed(1)}
          </span>
        ) : null}
      </button>
      <div className="recommendation-card-body">
        <div className="recommendation-meta">
          <StatusBadge status="connected">{getProviderLabel(item.provider)}</StatusBadge>
          <StatusBadge status="idle">{getMediaTypeLabel(mediaType)}</StatusBadge>
        </div>
        <h3>{item.title}</h3>
        {item.year && <p>{item.year}</p>}
        <button
          type="button"
          className="recommendation-search-btn"
          onClick={() => onOpenDetail(item)}
          aria-label={`查看${item.title}详情`}
          title="查看详情"
        >
          <Info size={16} />
        </button>
      </div>
    </article>
  );
}

function RecommendationsPage() {
  const navigate = useNavigate();
  const [provider, setProvider] = useState('douban');
  const [doubanCategory, setDoubanCategory] = useState('movie_hot');
  const [tmdbCategory, setTmdbCategory] = useState('trending_all');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  const fetchRecommendations = async () => {
    setLoading(true);
    setError('');
    try {
      const tmdbOption = TMDB_CATEGORY_OPTIONS.find(option => option.value === tmdbCategory) || TMDB_CATEGORY_OPTIONS[0];
      const category = provider === 'douban' ? doubanCategory : tmdbOption.category;
      const mediaType = provider === 'douban' ? 'all' : tmdbOption.mediaType;
      const response = await getPosterWall(category, { provider, media_type: mediaType });
      setItems(response.data.items || []);
      if (response.data.available === false) {
        setError(response.data.error || response.data.message || '推荐来源暂不可用');
      }
    } catch (err) {
      setError(getApiErrorMessage(err, '获取推荐失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [provider, doubanCategory, tmdbCategory]);

  const searchTmdbItem = (item) => {
    navigate(buildSearchUrl(item));
  };

  const openRecommendationDetail = async (item) => {
    if (!item) return;
    const itemProvider = item.provider || item.source;
    const mediaType = item.tmdb_type || item.media_type;
    const hasDoubanDetail = itemProvider === 'douban' && item.douban_id;
    const hasTmdbDetail = item.tmdb_id && mediaType;

    setDetailOpen(true);
    setDetail(item);
    setDetailError('');
    setDetailLoading(Boolean(hasDoubanDetail || hasTmdbDetail));
    if (!hasDoubanDetail && !hasTmdbDetail) return;

    try {
      if (hasDoubanDetail) {
        const response = await getDoubanDetail(item.douban_id, mediaType);
        setDetail(response.data.item || item);
        if (response.data.available === false) {
          setDetailError(response.data.error || '获取豆瓣详情失败');
        }
      } else {
        const response = await getTmdbDetail(mediaType, item.tmdb_id);
        setDetail(response.data);
      }
    } catch (err) {
      setDetailError(getApiErrorMessage(err, '获取影视详情失败'));
    } finally {
      setDetailLoading(false);
    }
  };

  const activeProvider = RECOMMENDATION_PROVIDERS.find(item => item.value === provider) || RECOMMENDATION_PROVIDERS[0];
  const movieCount = items.filter(item => (item.tmdb_type || item.media_type) === 'movie').length;
  const tvCount = items.filter(item => (item.tmdb_type || item.media_type) === 'tv').length;
  const categoryOptions = provider === 'douban' ? DOUBAN_CATEGORY_OPTIONS : TMDB_CATEGORY_OPTIONS;
  const activeCategoryValue = provider === 'douban' ? doubanCategory : tmdbCategory;
  const setActiveCategory = provider === 'douban' ? setDoubanCategory : setTmdbCategory;

  return (
    <div className="fade-in recommendations-page">
      <PageHeader
        eyebrow="Recommendation Sources"
        title="推荐"
        description="按来源查看近期热播与口碑内容。TMDB 与豆瓣并行展示，进入搜索时保留对应媒体上下文。"
        actions={<IconButton icon={RefreshCcw} className="btn-outline-secondary" onClick={fetchRecommendations} disabled={loading}>刷新</IconButton>}
      />

      <div className="recommendations-source-bar">
        <div className="recommendations-source-list" aria-label="推荐来源">
          {RECOMMENDATION_PROVIDERS.map(source => (
            <button
              key={source.value}
              type="button"
              className={provider === source.value ? 'active' : ''}
              onClick={() => {
                if (!source.enabled) return;
                setProvider(source.value);
              }}
              disabled={!source.enabled}
              title={source.label}
            >
              <span>{source.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="recommendations-category-bar" aria-label={`${activeProvider.label}推荐分类`}>
        {categoryOptions.map(option => (
          <button
            key={option.value}
            type="button"
            className={activeCategoryValue === option.value ? 'active' : ''}
            onClick={() => setActiveCategory(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {loading && <LoadingState label="正在加载推荐内容..." />}

      {!loading && error && (
        <EmptyState
          icon={Sparkles}
          title="推荐加载失败"
          description={error}
          actions={<IconButton icon={RefreshCcw} className="btn-primary" onClick={fetchRecommendations}>重试</IconButton>}
        />
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState icon={Sparkles} title="暂无推荐内容" description={`当前没有可展示的 ${activeProvider.label} 推荐内容。`} />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="recommendations-workbench">
          <main className="recommendations-main">
            <div className="recommendations-toolbar">
              <div>
                <h5>{activeProvider.label} 热播内容</h5>
                <p>共 {items.length} 部内容，结合入库状态和订阅状态快速进入搜索。</p>
              </div>
              <div className="recommendations-stat-strip">
                <span>来源 {activeProvider.label}</span>
                <span>电影 {movieCount}</span>
                <span>剧集 {tvCount}</span>
              </div>
            </div>
            <div className="recommendations-grid">
              {items.map(item => (
                <RecommendationCard
                  key={`${item.provider || item.tmdb_type}-${item.provider_id || item.tmdb_id || item.douban_id || item.title}`}
                  item={item}
                  onOpenDetail={openRecommendationDetail}
                />
              ))}
            </div>
          </main>
        </div>
      )}

      <TmdbDetailModal
        show={detailOpen}
        loading={detailLoading}
        detail={detail}
        error={detailError}
        onClose={() => setDetailOpen(false)}
        onSearch={searchTmdbItem}
      />
    </div>
  );
}

export default RecommendationsPage;
