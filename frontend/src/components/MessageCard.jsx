import React from 'react';
import toast from 'react-hot-toast';
import { Archive, CheckCircle2, Clipboard, ImagePlus, Link2, RefreshCcw, Search } from 'lucide-react';
import { matchPosterSingle, retryMessage } from '../api/messages';
import { transferResource } from '../api/transfers';
import { getApiErrorMessage } from '../api/errors';
import CopyToClipboard from './CopyToClipboard';
import { MediaLibraryStatus } from './ui';
import PosterEditView from './PosterEditView';
import { formatDateTime, truncateText } from '../utils/text';
import { getLibraryState } from '../utils/media';

function MessageCard({ message, onRetry, onClick }) {
  const [retrying, setRetrying] = React.useState(false);
  const [matching, setMatching] = React.useState(false); 
  const [isEditingPoster, setIsEditingPoster] = React.useState(false); // Inline edit mode

  const handleForward = async (e) => {
    e.stopPropagation();
    if (!message.resource_url) {
      toast.error('没有可用的资源链接进行转存。');
      return;
    }

    const toastId = toast.loading('正在发送转存请求...');

    try {
      await transferResource({ url: message.resource_url, title: message.title });
      toast.success('转存请求已发送成功！', { id: toastId });

    } catch (error) {
      console.error('Failed to forward link:', error);
      toast.error(`转存失败: ${getApiErrorMessage(error)}`, { id: toastId });
    }
  };

  const handleRetry = async (e) => {
    e.stopPropagation();
    setRetrying(true);
    const toastId = toast.loading('正在重新抓取该消息...');

    try {
      const response = await retryMessage({
        channel_name: message.channel_name,
        message_id: message.message_id
      });
      toast.success(`重试成功! 找到 ${response.data.links_found} 个链接`, { id: toastId });
      
      // Notify parent to refresh data
      if (onRetry) onRetry();

    } catch (error) {
      console.error('Retry failed:', error);
      toast.error(`重试失败: ${getApiErrorMessage(error)}`, { id: toastId });
    } finally {
      setRetrying(false);
    }
  };

  const handleMatchPosterSingle = async (e) => {
    e.stopPropagation();
    if (matching) return;
    
    setMatching(true);
    try {
      const response = await matchPosterSingle({ message_id: message.id }); // Use message.id not message.message_id
      if (response.data.status === 'success') {
        toast.success('海报匹配成功！');
        if (onRetry) onRetry(); 
      } else {
        toast.error('未找到海报');
      }
    } catch (error) {
      toast.error(`匹配失败: ${getApiErrorMessage(error)}`);
    } finally {
      setMatching(false);
    }
  };

  const ed2kLinks = message.links?.filter(l => l.url.startsWith('ed2k')) || [];
  const hasEd2kLinks = ed2kLinks.length > 0;

  const magnetLinks = message.links?.filter(l => l.url.startsWith('magnet:?xt=')) || [];
  const hasMagnetLinks = magnetLinks.length > 0;
  const libraryState = message.library_state || message.subscription_state;
  const isInLibrary = libraryState?.status === 'completed';
  const posterUrl = message.image_url || message.poster_url || message.thumbnail_url || message.cover_url;

  return (
    <div 
      className="message-card"
      onClick={onClick}
    >
      <div className="message-card-header">
        <span className="status-badge muted">
          {message.channel_name}
        </span>
        <small>
          {formatDateTime(message.publish_date)}
        </small>
      </div>

      {isEditingPoster ? (
        <div className="position-relative w-100 border-bottom" style={{ height: '300px', backgroundColor: 'var(--bg-surface-soft)' }}>
            <PosterEditView 
                initialQuery={message.title} 
                messageId={message.id} 
                onUpdate={() => {
                    if (onRetry) onRetry();
                }}
                onCancel={() => setIsEditingPoster(false)}
            />
        </div>
      ) : posterUrl ? (
        <div className="message-poster-wrap">
            {isInLibrary && (
              <span className="poster-corner-badge poster-corner-badge-left poster-corner-badge-success" aria-label="Jellyfin 已入库" title="Jellyfin 已入库">
                <CheckCircle2 size={16} />
              </span>
            )}
            <img 
                src={posterUrl} 
                alt={message.title}
                className="position-absolute top-0 start-0 w-100 h-100"
                style={{ objectFit: 'cover' }}
                loading="lazy"
                onError={(e) => {
                    e.target.onerror = null; 
                    e.target.style.display = 'none';
                    // Don't hide parent, maybe show placeholder or manual match button
                }}
            />
        </div>
      ) : (
        <div className="message-poster-wrap">
          {isInLibrary && (
            <span className="poster-corner-badge poster-corner-badge-left poster-corner-badge-success" aria-label="Jellyfin 已入库" title="Jellyfin 已入库">
              <CheckCircle2 size={16} />
            </span>
          )}
          <div className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center text-muted">
            <ImagePlus size={28} />
          </div>
        </div>
      )}

      <div className="message-card-body">
        <h5 className="message-card-title text-truncate-multiline">
            {message.title || '无标题'}
        </h5>
        {getLibraryState(message) && (
          <div className="mb-2">
            <MediaLibraryStatus state={libraryState} mediaType={message.tmdb_type} compact />
          </div>
        )}
        {message.tmdb_id && (
          <div className="small text-muted mb-2">
            TMDB {message.tmdb_id}{message.year ? ` · ${message.year}` : ''}
          </div>
        )}
        
        <p className="message-card-description text-truncate-multiline">
          {message.description || '无简介'}
        </p>
      </div>
      
      <div className="message-link-details" onClick={(e) => e.stopPropagation()}>
        {hasEd2kLinks && (
            <div className="mb-2">
            <details className="p-2 border rounded bg-light">
                <summary style={{ cursor: 'pointer', userSelect: 'none', listStyle: 'none' }} className="d-flex align-items-center justify-content-between small fw-bold text-primary">
                <span>
                    <Link2 size={14} className="me-1" /> ED2K 链接 ({ed2kLinks.length})
                </span>
                <small className="text-muted">展开</small>
                </summary>

                <div className="mt-2 pt-2 border-top">
                <CopyToClipboard
                    text={ed2kLinks.map(l => l.url).join('\n')}
                    className="btn btn-primary btn-sm w-100 mb-2 py-1"
                >
                    复制全部
                </CopyToClipboard>

                <div style={{ maxHeight: '150px', overflowY: 'auto' }} className="custom-scrollbar">
                    <ul className="list-unstyled mb-0 small">
                    {ed2kLinks.map((link, idx) => (
                        <li key={link.id || idx} className="d-flex justify-content-between align-items-center mb-1 p-1 hover-bg-gray rounded">
                        <span className="text-truncate text-muted me-2" style={{ maxWidth: '180px' }}>
                            {truncateText(link.url, 30)}
                        </span>
                    <CopyToClipboard
                            text={link.url}
                            className="btn btn-xs btn-link text-decoration-none p-0"
                        >
                            <Clipboard size={14} />
                        </CopyToClipboard>
                        </li>
                    ))}
                    </ul>
                </div>
                </div>
            </details>
            </div>
        )}

        {hasMagnetLinks && (
            <div>
            <details className="p-2 border rounded bg-light">
                <summary style={{ cursor: 'pointer', userSelect: 'none', listStyle: 'none' }} className="d-flex align-items-center justify-content-between small fw-bold text-warning">
                <span>
                    <Link2 size={14} className="me-1" /> 磁力链接 ({magnetLinks.length})
                </span>
                <small className="text-muted">展开</small>
                </summary>

                <div className="mt-2 pt-2 border-top">
                <CopyToClipboard
                    text={magnetLinks.map(l => l.url).join('\n')}
                    className="btn btn-warning btn-sm w-100 mb-2 py-1 text-white"
                >
                    复制全部
                </CopyToClipboard>

                <div style={{ maxHeight: '150px', overflowY: 'auto' }} className="custom-scrollbar">
                    <ul className="list-unstyled mb-0 small">
                    {magnetLinks.map((link, idx) => (
                        <li key={link.id || idx} className="d-flex justify-content-between align-items-center mb-1 p-1 hover-bg-gray rounded">
                        <span className="text-truncate text-muted me-2" style={{ maxWidth: '180px' }}>
                            {truncateText(link.url, 30)}
                        </span>
                        <CopyToClipboard
                            text={link.url}
                            className="btn btn-xs btn-link text-decoration-none p-0"
                        >
                            <Clipboard size={14} />
                        </CopyToClipboard>
                        </li>
                    ))}
                    </ul>
                </div>
                </div>
            </details>
            </div>
        )}
      </div>
      
      <div className="message-card-footer" onClick={(e) => e.stopPropagation()}>
        <div className="d-grid gap-2">
            {message.resource_url ? (
              <div className="d-flex gap-2 w-100">
                <CopyToClipboard
                  text={message.resource_url}
                  className="btn btn-success btn-sm flex-grow-1 d-flex align-items-center justify-content-center"
                >
                  <Clipboard size={14} /> 115资源
                </CopyToClipboard>
                <button onClick={handleForward} className="btn btn-info btn-sm text-white flex-grow-1 d-flex align-items-center justify-content-center">
                  <Archive size={14} /> 转存
                </button>
              </div>
            ) : (
                <div className="d-flex gap-2">
                     <button 
                        onClick={handleRetry} 
                        className="btn btn-outline-secondary btn-sm w-100" 
                        disabled={retrying}
                    >
                        {retrying ? <span className="spinner-border spinner-border-sm"></span> : <><RefreshCcw size={14} /> 重新获取</>}
                    </button>
                </div>
            )}
             
            <div className="card-mini-actions">
                <div className="d-flex gap-2">
                    {message.resource_url && (
                        <button 
                            onClick={handleRetry} 
                            className="btn btn-link btn-sm text-muted text-decoration-none p-0"
                            disabled={retrying}
                            style={{fontSize: '0.75rem'}}
                        >
                            {retrying ? '正在更新...' : '链接失效?'}
                        </button>
                    )}
                    
                    {/* 已有海报时，提供修改入口 */}
                    {posterUrl && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setIsEditingPoster(true);
                            }}
                            className="btn btn-link btn-sm text-muted text-decoration-none p-0"
                            style={{fontSize: '0.75rem'}}
                            title="手动搜索并替换当前海报"
                        >
                            修改海报
                        </button>
                    )}
                </div>
                
                {/* 仅当没有海报时显示补全按钮 */}
                {!posterUrl && (
                    <div className="ms-auto d-flex align-items-center">
                        <button 
                            onClick={(e) => {
                                e.stopPropagation();
                                setIsEditingPoster(true);
                            }} 
                            className="btn btn-link btn-sm text-secondary text-decoration-none p-0 me-2"
                            style={{fontSize: '0.75rem'}}
                        >
                            <Search size={13} /> 手动
                        </button>
                        <button 
                            onClick={handleMatchPosterSingle} 
                            className="btn btn-link btn-sm text-primary text-decoration-none p-0"
                            disabled={matching}
                            style={{fontSize: '0.75rem'}}
                        >
                            {matching ? '匹配中...' : <><ImagePlus size={13} /> 自动补全</>}
                        </button>
                    </div>
                )}
            </div>
        </div>
      </div>
    </div>
  );
}

export default MessageCard;
