import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

function MobileBottomSheet({ open, title, children, footer, onClose }) {
  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', handleKeyDown);
    document.body.classList.add('bottom-sheet-open');
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.classList.remove('bottom-sheet-open');
    };
  }, [open, onClose]);

  if (!open) return null;
  const footerCount = React.Children.count(footer);

  return createPortal(
    <div className="bottom-sheet-backdrop" onClick={onClose}>
      <section className="bottom-sheet" role="dialog" aria-modal="true" aria-label={title || '详情'} onClick={event => event.stopPropagation()}>
        <div className="bottom-sheet-handle" />
        <header className="bottom-sheet-header">
          <h3>{title || '详情'}</h3>
          <button type="button" className="bottom-sheet-close" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <div className="bottom-sheet-body">{children}</div>
        {footer && <footer className={`bottom-sheet-footer count-${footerCount}`}>{footer}</footer>}
      </section>
    </div>,
    document.body,
  );
}

export default MobileBottomSheet;
