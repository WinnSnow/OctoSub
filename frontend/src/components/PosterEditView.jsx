import React from 'react';
import toast from 'react-hot-toast';
import { getApiErrorMessage } from '../api/errors';
import { updatePoster } from '../api/messages';
import { searchTmdb } from '../api/search';

function PosterEditView({ initialQuery, messageId, onUpdate, onCancel }) {
  const [query, setQuery] = React.useState(initialQuery || '');
  const [results, setResults] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [updating, setUpdating] = React.useState(false);

  const handleSearch = React.useCallback(async (searchQuery) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const response = await searchTmdb(searchQuery);
      setResults(response.data.results || []);
    } catch (error) {
      toast.error(`搜索失败: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (initialQuery) handleSearch(initialQuery);
  }, [handleSearch, initialQuery]);

  const parseYear = (year) => {
    if (!year || year === '未知年份') return null;
    const parsed = parseInt(year, 10);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const handleSelect = async (item) => {
    if (updating) return;
    setUpdating(true);
    try {
      await updatePoster({
        message_id: messageId,
        image_url: item.poster_url,
        tmdb_id: item.id,
        tmdb_type: item.tmdb_type,
        year: parseYear(item.year),
      });
      toast.success('更新成功');
      onUpdate();
      onCancel();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '更新失败'));
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="bg-white h-100 d-flex flex-column" onClick={event => event.stopPropagation()}>
      <div className="p-2 border-bottom d-flex gap-2 bg-light">
        <input
          type="text"
          className="form-control form-control-sm"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && handleSearch(query)}
          placeholder="搜片名..."
          autoFocus
        />
        <button className="btn btn-primary btn-sm" onClick={() => handleSearch(query)} disabled={loading}>
          {loading ? '...' : '搜'}
        </button>
        <button className="btn btn-outline-secondary btn-sm" onClick={onCancel}>
          x
        </button>
      </div>

      <div className="flex-grow-1 overflow-auto custom-scrollbar p-1" style={{ minHeight: '200px', maxHeight: '300px' }}>
        {results.length > 0 ? (
          <div className="row row-cols-3 g-2">
            {results.map(item => (
              <div key={`${item.tmdb_type}-${item.id}`} className="col">
                <div
                  className="card h-100 border-0 cursor-pointer position-relative"
                  onClick={() => handleSelect(item)}
                >
                  <img src={item.poster_url} className="card-img-top rounded" style={{ aspectRatio: '2/3', objectFit: 'cover' }} alt={item.title} />
                  <div className="small text-truncate mt-1 text-center" style={{ fontSize: '0.6rem' }}>{item.title} ({item.year})</div>
                  <div className="small text-muted text-center" style={{ fontSize: '0.55rem' }}>{item.type} · TMDB {item.id}</div>
                  {updating && (
                    <div className="position-absolute top-0 start-0 w-100 h-100 bg-white opacity-75 d-flex align-items-center justify-content-center">
                      <div className="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          !loading && <div className="text-center text-muted small py-4">无结果，换个词试试</div>
        )}
      </div>
    </div>
  );
}

export default PosterEditView;
