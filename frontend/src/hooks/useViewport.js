import { useEffect, useState } from 'react';

function getViewportWidth() {
  if (typeof window === 'undefined') return 1024;
  return window.innerWidth || document.documentElement.clientWidth || 1024;
}

export function useIsNarrowViewport(maxWidth = 767.98) {
  const [isNarrow, setIsNarrow] = useState(() => getViewportWidth() <= maxWidth);

  useEffect(() => {
    const handleResize = () => {
      setIsNarrow(getViewportWidth() <= maxWidth);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [maxWidth]);

  return isNarrow;
}
