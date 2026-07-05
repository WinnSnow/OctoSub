import React, { useState } from 'react';
import { CalendarDays, Clock3, ExternalLink, ImageOff, Search, Star, X } from 'lucide-react';
import { IconButton, LoadingState } from './ui';

const DEFAULT_EPISODE_VISIBLE_COUNT = 3;

function joinList(value, limit = 6) {
  if (Array.isArray(value)) {
    return value.filter(Boolean).slice(0, limit).join(' / ');
  }
  return value || '';
}

function formatCount(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '';
  if (number >= 10000) return `${(number / 10000).toFixed(number >= 100000 ? 0 : 1)} 万人评价`;
  return `${number} 人评价`;
}

function DetailFactList({ detail }) {
  const facts = [
    { label: '原名', value: detail.original_title },
    { label: '别名', value: joinList(detail.aliases, 3) },
    { label: '上映', value: detail.pubdate || joinList(detail.pubdates, 2) },
    { label: '地区', value: joinList(detail.countries) },
    { label: '语言', value: joinList(detail.languages) },
    { label: '片长', value: joinList(detail.durations, 3) || (detail.runtime ? `${detail.runtime} 分钟` : '') },
    { label: '集数', value: detail.episode_count ? `${detail.episode_count} 集` : '' },
    { label: '评价', value: formatCount(detail.douban_rating_count) },
  ].filter(item => item.value);

  if (!facts.length) return null;
  return (
    <dl className="tmdb-fact-list">
      {facts.map(item => (
        <div className="tmdb-fact-row" key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function EpisodeList({ season }) {
  const [expanded, setExpanded] = useState(false);
  const episodes = season.episodes || [];
  const visibleEpisodes = expanded ? episodes : episodes.slice(0, DEFAULT_EPISODE_VISIBLE_COUNT);
  if (episodes.length === 0) {
    return <div className="tmdb-episode-empty">暂无每集详情。</div>;
  }
  return (
    <div className="tmdb-episode-block">
      <div className="tmdb-episode-head">
        <strong>每集详情</strong>
        <span>{episodes.length} 集</span>
      </div>
      <div className="tmdb-episode-list">
        {visibleEpisodes.map(episode => (
          <article className="tmdb-episode-card" key={episode.episode_number}>
            <div className="tmdb-episode-still">
              {episode.still_url ? <img src={episode.still_url} alt={episode.name} /> : <ImageOff size={18} />}
            </div>
            <div className="tmdb-episode-copy">
              <div className="tmdb-episode-title-row">
                <span className="tmdb-episode-number">E{String(episode.episode_number).padStart(2, '0')}</span>
                <h6>{episode.name || `第 ${episode.episode_number} 集`}</h6>
              </div>
              <div className="tmdb-episode-meta">
                <span><CalendarDays size={13} />{episode.air_date || '暂无播出日期'}</span>
                {episode.runtime ? <span><Clock3 size={13} />{episode.runtime} 分钟</span> : null}
                {episode.vote_average ? <span><Star size={13} />{Number(episode.vote_average).toFixed(1)}</span> : null}
              </div>
              <p>{episode.overview || '暂无本集简介。'}</p>
            </div>
          </article>
        ))}
      </div>
      {episodes.length > DEFAULT_EPISODE_VISIBLE_COUNT && (
        <button type="button" className="tmdb-episode-toggle" onClick={() => setExpanded(value => !value)}>
          {expanded ? '收起' : `展开全部 ${episodes.length} 集`}
        </button>
      )}
    </div>
  );
}

function SeasonList({ seasons }) {
  if (!seasons?.length) return null;
  const totalEpisodes = seasons.reduce((sum, item) => sum + Number(item.episode_count || 0), 0);
  return (
    <div className="tmdb-season-block">
      <div className="tmdb-season-summary">
        <strong>分季信息</strong>
        <span>共 {seasons.length} 季，{totalEpisodes} 集</span>
      </div>
      <div className="tmdb-season-list">
        {seasons.map(season => (
          <article className="tmdb-season-card" key={season.season_number}>
            <div className="tmdb-season-poster">
              {season.poster_url ? <img src={season.poster_url} alt={season.name} /> : <X size={18} />}
            </div>
            <div className="tmdb-season-copy">
              <div className="tmdb-season-title-row">
                <h6>{season.name || `第 ${season.season_number} 季`}</h6>
                <span>{Number(season.episode_count || 0)} 集</span>
              </div>
              {season.air_date && (
                <div className="tmdb-season-date">
                  <CalendarDays size={13} />
                  {season.air_date}
                </div>
              )}
              <p>{season.overview || '暂无本季简介。'}</p>
              <EpisodeList season={season} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function TmdbDetailModal({ show, loading, detail, error, onClose, onSearch }) {
  if (!show) return null;
  const sourceLabel = detail?.metadata_source === 'douban' || detail?.provider === 'douban' ? '豆瓣' : 'TMDB';
  const mediaType = detail?.tmdb_type || detail?.media_type;
  const rating = detail?.vote_average || detail?.douban_rating;
  const externalUrl = detail?.douban_url || detail?.url;
  return (
    <div
      className="modal fade show d-block tmdb-detail-modal"
      tabIndex="-1"
      role="dialog"
      aria-modal="true"
      onMouseDown={onClose}
    >
      <div className="modal-dialog tmdb-detail-dialog modal-dialog-centered" onMouseDown={event => event.stopPropagation()}>
        <div className="modal-content">
          <div className="modal-header">
            <div>
              <div className="page-eyebrow">{sourceLabel}</div>
              <h5 className="modal-title">{detail?.title || '影视详情'}</h5>
            </div>
            <button type="button" className="btn-close" aria-label="关闭" onClick={onClose}></button>
          </div>
          <div className="modal-body">
            {loading && <LoadingState label="正在加载详情..." />}
            {!loading && error && <div className="alert alert-warning mb-0">{error}</div>}
            {!loading && !error && detail && (
              <div className="tmdb-detail-grid">
                <div className="tmdb-detail-poster">
                  {detail.poster_url ? <img src={detail.poster_url} alt={detail.title} /> : <X size={28} />}
                </div>
                <div className="tmdb-detail-copy">
                  <div className="d-flex gap-2 flex-wrap mb-2">
                    <span className="status-badge muted">{mediaType === 'tv' ? '剧集' : '电影'}</span>
                    {detail.year && <span className="status-badge muted">{detail.year}</span>}
                    {rating ? <span className="status-badge warning">{Number(rating).toFixed(1)}</span> : null}
                  </div>
                  <p>{detail.overview || '暂无简介。'}</p>
                  {detail.genres?.length > 0 && (
                    <div className="chip-row mb-3">
                      {detail.genres.map(item => <span className="chip" key={item}>{item}</span>)}
                    </div>
                  )}
                  <DetailFactList detail={detail} />
                  {(detail.directors?.length > 0 || detail.writers?.length > 0 || detail.actors?.length > 0) && (
                    <div className="tmdb-credit-list">
                      {detail.directors?.length > 0 && <div><span>导演</span><strong>{detail.directors.join(' / ')}</strong></div>}
                      {detail.writers?.length > 0 && <div><span>编剧</span><strong>{detail.writers.join(' / ')}</strong></div>}
                      {detail.actors?.length > 0 && <div><span>主演</span><strong>{detail.actors.slice(0, 8).join(' / ')}</strong></div>}
                    </div>
                  )}
                  {externalUrl && (
                    <a className="tmdb-external-link" href={externalUrl} target="_blank" rel="noreferrer">
                      <ExternalLink size={14} />
                      打开{sourceLabel}条目
                    </a>
                  )}
                  {mediaType === 'tv' && <SeasonList seasons={detail.seasons} />}
                </div>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-outline-secondary" onClick={onClose}>关闭</button>
            <IconButton icon={Search} className="btn-primary" onClick={() => detail && onSearch(detail)} disabled={!detail}>
              搜索资源
            </IconButton>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TmdbDetailModal;
