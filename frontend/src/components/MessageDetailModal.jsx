import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Clipboard, ExternalLink, Link2, X } from 'lucide-react';
import { formatDateTime, truncateText } from '../utils/text';

// Simple Modal Component using Bootstrap classes
const MessageDetailModal = ({ show, onClose, message }) => {
  const modalRef = useRef(null);

  // Close on Escape key
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    if (show) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = 'unset';
    };
  }, [show, onClose]);

  // Close on click outside
  const handleBackdropClick = (e) => {
    if (modalRef.current && !modalRef.current.contains(e.target)) {
      onClose();
    }
  };

  if (!show || !message) return null;

  const posterUrl = message.image_url || message.poster_url || message.thumbnail_url || message.cover_url;

  const copyToClipboard = (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text);
    } else {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
    }
    // You might want to show a toast here, but we'll keep it simple
    // or pass a callback to parent to show toast
  };

  return createPortal(
    <div 
      className="modal fade show" 
      style={{ display: 'block', backgroundColor: 'rgba(0,0,0,0.5)' }} 
      tabIndex="-1" 
      onClick={handleBackdropClick}
    >
      <div className="modal-dialog modal-dialog-centered modal-lg modal-dialog-scrollable" ref={modalRef}>
        <div className="modal-content shadow-lg border-0 rounded-3">
          
          {/* Header */}
          <div className="modal-header border-bottom-0 pb-0">
            <div className="d-flex flex-column w-100">
                <div className="d-flex justify-content-between align-items-start">
                    <span className="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill mb-2">
                        {message.channel_name}
                    </span>
                    <button type="button" className="btn btn-light btn-sm" onClick={onClose} aria-label="Close"><X size={16} /></button>
                </div>
                <h4 className="modal-title fw-bold text-break pe-3">{message.title || '无标题'}</h4>
                <small className="text-muted mt-1">
                    发布于: {formatDateTime(message.publish_date)}
                </small>
            </div>
          </div>

          {/* Body */}
          <div className="modal-body py-4">
            <div className="row">
                {/* Poster in Modal */}
                {posterUrl && (
                    <div className="col-md-4 mb-3 mb-md-0">
                        <img 
                            src={posterUrl} 
                            alt={message.title} 
                            className="img-fluid rounded shadow-sm w-100"
                            style={{ objectFit: 'cover' }}
                        />
                    </div>
                )}
                
                <div className={posterUrl ? "col-md-8" : "col-12"}>
                    {/* Description */}
                    <div className="mb-4">
                        <h6 className="fw-bold text-secondary mb-2">简介内容</h6>
                        <div className="p-3 bg-light rounded-3 text-break" style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem', lineHeight: '1.6' }}>
                            {message.description || '暂无简介'}
                        </div>
                    </div>

                    {/* Links Section */}
                    {(message.links && message.links.length > 0) && (
                        <div>
                            <h6 className="fw-bold text-secondary mb-2">资源链接 ({message.links.length})</h6>
                            <div className="card border-0 bg-light">
                                <div className="card-body p-2">
                                    <ul className="list-group list-group-flush bg-transparent">
                                        {message.links.map((link, index) => (
                                            <li key={index} className="list-group-item bg-transparent d-flex justify-content-between align-items-center py-2 px-2 border-bottom-0 mb-1 rounded hover-bg-white">
                                                <div className="d-flex align-items-center overflow-hidden me-2">
                                                    <span className="badge bg-secondary me-2 d-inline-flex align-items-center gap-1" style={{minWidth: '58px'}}><Link2 size={12} />{link.url.startsWith('ed2k') ? 'ED2K' : (link.url.startsWith('magnet') ? '磁力' : '链接')}</span>
                                                    <span className="text-muted small text-truncate">{truncateText(link.url, 50)}</span>
                                                </div>
                                                <button 
                                                    className="btn btn-sm btn-outline-primary py-0 px-2" 
                                                    style={{fontSize: '0.8rem'}}
                                                    onClick={() => copyToClipboard(link.url)}
                                                >
                                                    <Clipboard size={14} /> 复制
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
          </div>

          {/* Footer */}
          <div className="modal-footer border-top-0 pt-0 pb-4 px-4">
            <button type="button" className="btn btn-light" onClick={onClose}>关闭</button>
            {message.resource_url && (
                <button 
                    type="button" 
                    className="btn btn-primary"
                    onClick={() => {
                        copyToClipboard(message.resource_url);
                        window.open(message.resource_url, '_blank', 'noopener,noreferrer');
                    }}
                >
                    <ExternalLink size={16} /> 访问原始链接
                </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default MessageDetailModal;
