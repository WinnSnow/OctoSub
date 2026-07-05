import React from 'react';
import { CheckCircle2, Clapperboard, Search } from 'lucide-react';

import { MediaLibraryStatus, MediaPoster, Panel } from '../ui';
import { DEFAULT_SUBSCRIPTION_CONFIDENCE } from '../../config/app';
import { getTmdbMediaType } from '../../utils/subscriptions';
import { getMediaTypeBadgeClass } from '../../utils/media';

function SearchBadge({ item }) {
  const state = item.subscription_state;
  if (!state) return null;
  return <MediaLibraryStatus state={state} mediaType={getTmdbMediaType(item.type)} compact />;
}

function EpisodeMarker({ label, value }) {
  if (!value?.season_number || !value?.episode_number) return null;
  return (
    <span className="badge bg-light text-dark border">
      {label} S{String(value.season_number).padStart(2, '0')}E{String(value.episode_number).padStart(2, '0')}
      {value.air_date ? ` · ${value.air_date}` : ''}
    </span>
  );
}

function TvSeasonPicker({ detail, loading, selectedSeasons, onChange }) {
  const seasons = detail?.seasons || [];
  if (loading) {
    return (
      <div className="alert alert-light border">
        正在加载剧集季信息...
      </div>
    );
  }
  if (!detail) return null;
  if (!seasons.length) {
    return (
      <div className="alert alert-warning">
        未获取到可订阅的季信息，无法创建精准剧集订阅。
      </div>
    );
  }

  const selected = new Set(selectedSeasons || []);
  const toggleSeason = (seasonNumber) => {
    const next = new Set(selected);
    if (next.has(seasonNumber)) {
      next.delete(seasonNumber);
    } else {
      next.add(seasonNumber);
    }
    onChange([...next].sort((a, b) => a - b));
  };

  return (
    <div className="mt-3">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
        <strong>选择订阅季</strong>
        <EpisodeMarker label="最近更新" value={detail.last_episode_to_air} />
        <EpisodeMarker label="下一集" value={detail.next_episode_to_air} />
        <button type="button" className="btn btn-sm btn-outline-secondary ms-auto" onClick={() => onChange(seasons.map(season => season.season_number))}>
          全选
        </button>
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => onChange([])}>
          清空
        </button>
      </div>
      <div className="row g-2">
        {seasons.map((season) => (
          <div className="col-md-6" key={season.season_number}>
            <label className={`season-select-card ${selected.has(season.season_number) ? 'selected' : ''}`}>
              <input
                type="checkbox"
                className="form-check-input"
                checked={selected.has(season.season_number)}
                onChange={() => toggleSeason(season.season_number)}
              />
              <div>
                <div className="fw-semibold">第 {season.season_number} 季</div>
                <div className="small text-muted">
                  {season.episode_count} 集{season.air_date ? ` · 首播 ${season.air_date}` : ''}
                </div>
                {season.overview && <div className="small text-muted text-truncate-multiline mt-1">{season.overview}</div>}
              </div>
            </label>
          </div>
        ))}
      </div>
      {seasons.length > 1 && (!selectedSeasons || selectedSeasons.length === 0) && (
        <div className="small text-danger mt-2">多季剧集需要手动选择至少一季。</div>
      )}
    </div>
  );
}

function SubscriptionForm({
  editingId,
  formData,
  selectedTmdb,
  tmdbQuery,
  tmdbResults,
  tmdbSearching,
  tmdbTvDetail,
  tmdbDetailLoading,
  onSubmit,
  onCancel,
  onFormChange,
  onTmdbQueryChange,
  onTmdbSearch,
  onSelectTmdb,
  onClearTmdb,
}) {
  return (
    <Panel className="mb-4">
      <h5 className="card-title">{editingId ? '编辑订阅' : '新建订阅'}</h5>

      {!selectedTmdb && (
        <div className="alert alert-info">
          <h6 className="alert-heading d-flex align-items-center gap-2"><Clapperboard size={16} /> 精准订阅（推荐）</h6>
          <p className="mb-2">先搜索 TMDB 选择具体作品，可以精准区分同名不同版本（如"镖人2023动画"和"镖人2026电影"）</p>
          <div className="row g-2">
            <div className="col-md-8">
              <input
                type="text"
                className="form-control"
                placeholder="输入影视名称，如：镖人"
                value={tmdbQuery}
                onChange={(event) => onTmdbQueryChange(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && onTmdbSearch()}
              />
            </div>
            <div className="col-md-4">
              <button type="button" className="btn btn-primary w-100" onClick={onTmdbSearch} disabled={tmdbSearching}>
                {tmdbSearching ? '搜索中...' : <><Search size={16} /> 搜索 TMDB</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {tmdbResults.length > 0 && !selectedTmdb && (
        <div className="mb-3">
          <h6>选择要订阅的作品：</h6>
          <div className="row g-3">
            {tmdbResults.map((item) => (
              <div key={item.id} className="col-md-6 col-lg-4">
                <div className="card h-100 cursor-pointer" onClick={() => onSelectTmdb(item)} style={{ cursor: 'pointer' }}>
                  <div className="row g-0">
                    <div className="col-4">
                      <img src={item.poster_url} alt={item.title} className="img-fluid rounded-start" style={{ height: '150px', objectFit: 'cover' }} />
                    </div>
                    <div className="col-8">
                      <div className="card-body p-2">
                        <h6 className="card-title mb-1" style={{ fontSize: '0.9rem' }}>
                          {item.title}
                        </h6>
                        <p className="card-text mb-1">
                          <span className={`badge ${getMediaTypeBadgeClass(getTmdbMediaType(item.type))}`}>
                            {item.type}
                          </span>
                          <span className="ms-1 small text-muted">{item.year}</span>
                        </p>
                        <div className="mb-1"><SearchBadge item={item} /></div>
                        <p className="card-text small text-muted mb-0" style={{ fontSize: '0.75rem' }}>
                          {item.overview}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <hr className="my-3" />
        </div>
      )}

      {selectedTmdb && (
        <div className="alert alert-success d-flex align-items-center">
          <div className="me-3"><MediaPoster src={selectedTmdb.poster_url} title={selectedTmdb.title} size="md" /></div>
          <div className="flex-grow-1">
            <h6 className="mb-1 d-flex align-items-center gap-2"><CheckCircle2 size={16} /> 已选择：{selectedTmdb.title}</h6>
            <p className="mb-0 small">
              <span className={`badge ${getMediaTypeBadgeClass(getTmdbMediaType(selectedTmdb.type))}`}>
                {selectedTmdb.type}
              </span>
              <span className="ms-2">{selectedTmdb.year}</span>
              <span className="ms-2 text-muted">TMDB ID: {selectedTmdb.id}</span>
            </p>
          </div>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onClearTmdb}>
            重新选择
          </button>
        </div>
      )}

      {selectedTmdb && getTmdbMediaType(selectedTmdb.type) === 'tv' && (
        <TvSeasonPicker
          detail={tmdbTvDetail}
          loading={tmdbDetailLoading}
          selectedSeasons={formData.target_seasons || []}
          onChange={(target_seasons) => onFormChange({ target_seasons })}
        />
      )}

      <form onSubmit={onSubmit}>
        <div className="row g-3">
          <div className="col-md-4">
            <label className="form-label">订阅关键词 *</label>
            <input
              type="text"
              className="form-control"
              value={formData.keyword}
              onChange={(event) => onFormChange({ keyword: event.target.value })}
              placeholder="如：庆余年"
              required
              disabled={!!selectedTmdb}
            />
            <small className="text-muted">
              {selectedTmdb ? 'TMDB 模式已自动填充' : '系统会搜索包含此关键词的资源'}
            </small>
          </div>

          <div className="col-md-3">
            <label className="form-label">媒体类型</label>
            <select className="form-select" value={formData.media_type} onChange={(event) => onFormChange({ media_type: event.target.value })} disabled={!!selectedTmdb}>
              <option value="tv">剧集</option>
              <option value="movie">电影</option>
            </select>
          </div>

          <div className="col-md-5">
            <label className="form-label">质量过滤（可选）</label>
            <input
              type="text"
              className="form-control"
              value={formData.quality_filter}
              onChange={(event) => onFormChange({ quality_filter: event.target.value })}
              placeholder="如：4K|2160p|1080p"
            />
            <small className="text-muted">正则表达式，留空不过滤</small>
          </div>
        </div>

        <div className="row g-3 mt-1">
          <div className="col-md-3">
            <label className="form-label">订阅状态</label>
            <div className="form-check form-switch">
              <input className="form-check-input" type="checkbox" checked={formData.enabled} onChange={(event) => onFormChange({ enabled: event.target.checked })} />
              <label className="form-check-label">启用检查</label>
            </div>
          </div>

          <div className="col-md-3">
            <label className="form-label">自动转存</label>
            <div className="form-check form-switch">
              <input className="form-check-input" type="checkbox" checked={formData.auto_transfer} onChange={(event) => onFormChange({ auto_transfer: event.target.checked })} />
              <label className="form-check-label">高置信自动发送</label>
            </div>
          </div>

          <div className="col-md-3">
            <label className="form-label">自动阈值</label>
            <input
              type="number"
              className="form-control"
              min="0"
              max="1"
              step="0.01"
              value={formData.min_confidence}
              onChange={(event) => onFormChange({ min_confidence: Number(event.target.value) })}
            />
            <small className="text-muted">默认 {DEFAULT_SUBSCRIPTION_CONFIDENCE}，低于阈值进入待确认</small>
          </div>
        </div>

        <div className="subscription-form-footer d-flex gap-2 mt-3">
          <button type="submit" className="btn btn-primary">
            {editingId ? '更新' : '创建'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            取消
          </button>
          {!selectedTmdb && (
            <small className="text-muted align-self-center ms-2">
              提示：不选择 TMDB 将使用关键词匹配（可能不够精准）
            </small>
          )}
        </div>
      </form>
    </Panel>
  );
}

export default SubscriptionForm;
