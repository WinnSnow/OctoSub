import React from 'react';

import { getPosterStateLabel, POSTER_CATEGORIES } from '../../utils/media';
import { LoadingState } from '../ui';

function PosterWallSection({
  posterWall,
  posterWallError,
  posterCategory,
  posterLoading,
  onCategoryChange,
  onSearchPoster,
}) {
  const isDouban = String(posterCategory || '').startsWith('douban_');
  return (
    <section className="poster-wall-section">
      <div className="poster-wall-header">
        <div>
          <h2>{isDouban ? '豆瓣推荐' : 'TMDB 海报墙'}</h2>
          <p>点击海报后会用片名搜索 115 分享链接。</p>
        </div>
        <div className="segmented-control compact">
          {POSTER_CATEGORIES.map(({ value, label }) => (
            <button
              key={value}
              className={posterCategory === value ? 'active' : ''}
              onClick={() => onCategoryChange(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {posterLoading && <LoadingState label="正在加载海报墙..." />}
      {!posterLoading && posterWallError && (
        <div className="alert alert-warning py-2">
          {posterWallError}
        </div>
      )}
      {!posterLoading && posterWall.length > 0 && (
        <div className="poster-wall-grid">
          {posterWall.map((item) => (
            <button className="poster-wall-card" key={`${item.provider || item.tmdb_type}-${item.provider_id || item.tmdb_id || item.douban_id || item.title}`} onClick={() => onSearchPoster(item)}>
              <img src={item.poster_url} alt={item.title} loading="lazy" />
              {getPosterStateLabel(item) && (
                <span className={`poster-wall-state ${(item.library_state || item.subscription_state).status === 'completed' ? 'completed' : 'active'}`}>
                  {getPosterStateLabel(item)}
                </span>
              )}
              <span className="poster-wall-title">{item.title}</span>
              <small>
                {item.year || ''}
                {item.douban_rating ? ` · 豆瓣 ${item.douban_rating}` : ''}
              </small>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

export default PosterWallSection;
