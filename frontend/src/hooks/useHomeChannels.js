import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { getChannels, getPublicChannels } from '../api/channels';

export function useHomeChannels({ mode, runSearch }) {
  const [channels, setChannels] = useState([]);
  const [selectedChannels, setSelectedChannels] = useState([]);
  const [localSourceFilter, setLocalSourceFilter] = useState('all');

  const fetchChannels = useCallback(async () => {
    const response = await getPublicChannels();
    setChannels(response.data);
  }, []);

  useEffect(() => {
    fetchChannels().catch(async () => {
      try {
        const response = await getChannels();
        setChannels(response.data);
      } catch {
        toast.error('获取公开频道列表失败');
      }
    });
  }, [fetchChannels]);

  const toggleChannel = (channel) => {
    setSelectedChannels(prev => prev.includes(channel) ? prev.filter(item => item !== channel) : [...prev, channel]);
  };

  const selectLocalSource = useCallback((source) => {
    const nextSource = source || 'all';
    setLocalSourceFilter(nextSource);
    if (mode === 'local') {
      return runSearch({ nextPage: 1, overrideLocalSourceFilter: nextSource });
    }
    return Promise.resolve();
  }, [mode, runSearch]);

  return {
    channels,
    selectedChannels,
    localSourceFilter,
    setSelectedChannels,
    setLocalSourceFilter,
    toggleChannel,
    selectLocalSource,
  };
}
