import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';

import { getApiErrorMessage } from '../api/errors';
import { getTmdbTvDetail, searchTmdb } from '../api/search';
import { createSubscription, updateSubscription } from '../api/subscriptions';
import {
  createEmptySubscriptionForm,
  createSelectedTmdbFromSubscription,
  createSubscriptionFormFromRecord,
  createSubscriptionFormFromTmdb,
  getTmdbMediaType,
} from '../utils/subscriptions';

export function useSubscriptionFormController({
  refreshSubscriptions,
  startLifecycleRefresh,
}) {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState(createEmptySubscriptionForm);
  const [tmdbQuery, setTmdbQuery] = useState('');
  const [tmdbResults, setTmdbResults] = useState([]);
  const [tmdbSearching, setTmdbSearching] = useState(false);
  const [selectedTmdb, setSelectedTmdb] = useState(null);
  const [tmdbTvDetail, setTmdbTvDetail] = useState(null);
  const [tmdbDetailLoading, setTmdbDetailLoading] = useState(false);

  const resetForm = useCallback(() => {
    setFormData(createEmptySubscriptionForm());
    setTmdbQuery('');
    setTmdbResults([]);
    setSelectedTmdb(null);
    setTmdbTvDetail(null);
    setTmdbDetailLoading(false);
    setShowForm(false);
    setEditingId(null);
  }, []);

  const handleTmdbSearch = async () => {
    if (!tmdbQuery.trim()) {
      toast.error('请输入要搜索的影视名称');
      return;
    }

    setTmdbSearching(true);
    try {
      const response = await searchTmdb(tmdbQuery.trim());
      setTmdbResults(response.data.results || []);
      if ((response.data.results || []).length === 0) {
        toast('未找到匹配的作品，请尝试其他关键词', { icon: 'ℹ️' });
      }
    } catch (error) {
      toast.error('TMDB 搜索失败');
    } finally {
      setTmdbSearching(false);
    }
  };

  const handleSelectTmdb = async (item) => {
    setSelectedTmdb(item);
    setFormData(prev => createSubscriptionFormFromTmdb(item, prev));
    setTmdbTvDetail(null);
    toast.success(`已选择: ${item.title} (${item.year})`);
    if (getTmdbMediaType(item.type) !== 'tv') return;
    setTmdbDetailLoading(true);
    try {
      const response = await getTmdbTvDetail(item.id);
      const detail = response.data;
      const seasons = detail?.seasons || [];
      setTmdbTvDetail(detail);
      setFormData(prev => ({
        ...prev,
        target_seasons: seasons.length === 1 ? [seasons[0].season_number] : [],
      }));
    } catch (error) {
      toast.error(getApiErrorMessage(error, '获取剧集季信息失败'));
    } finally {
      setTmdbDetailLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.keyword.trim()) {
      toast.error('请输入订阅关键词');
      return;
    }
    if (formData.media_type === 'tv' && formData.tmdb_id) {
      const keepsLegacySeasonScope = editingId && formData.target_seasons === null;
      if (tmdbDetailLoading) {
        toast.error('剧集季信息仍在加载');
        return;
      }
      if (!keepsLegacySeasonScope && (!Array.isArray(formData.target_seasons) || formData.target_seasons.length === 0)) {
        toast.error('请选择要订阅的季');
        return;
      }
    }

    try {
      let savedSubscription;
      if (editingId) {
        const response = await updateSubscription(editingId, formData);
        savedSubscription = response.data;
        toast.success('订阅已更新');
      } else {
        const response = await createSubscription(formData);
        savedSubscription = response.data;
        toast.success('订阅已创建');
      }

      resetForm();
      await refreshSubscriptions();
      if (savedSubscription?.id) {
        await startLifecycleRefresh(savedSubscription.id, `同步订阅状态：${savedSubscription.keyword}`);
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, '操作失败'));
    }
  };

  const handleEdit = async (subscription) => {
    setFormData(createSubscriptionFormFromRecord(subscription));
    const selected = createSelectedTmdbFromSubscription(subscription);
    setSelectedTmdb(selected);
    setTmdbTvDetail(null);
    setEditingId(subscription.id);
    setShowForm(true);

    if (selected && subscription.media_type === 'tv') {
      setTmdbDetailLoading(true);
      try {
        const response = await getTmdbTvDetail(selected.id);
        setTmdbTvDetail(response.data);
      } catch (error) {
        toast.error(getApiErrorMessage(error, '获取剧集季信息失败'));
      } finally {
        setTmdbDetailLoading(false);
      }
    }
  };

  const handleClearTmdb = () => {
    setSelectedTmdb(null);
    setFormData(prev => ({
      ...prev,
      tmdb_id: null,
      tmdb_type: null,
      year: null,
      poster_url: null,
      target_seasons: null,
    }));
    setTmdbTvDetail(null);
  };

  return {
    showForm,
    setShowForm,
    editingId,
    formData,
    selectedTmdb,
    tmdbQuery,
    tmdbResults,
    tmdbSearching,
    tmdbTvDetail,
    tmdbDetailLoading,
    handleSubmit,
    handleCancel: resetForm,
    handleEdit,
    handleFormChange: patch => setFormData(prev => ({ ...prev, ...patch })),
    setTmdbQuery,
    handleTmdbSearch,
    handleSelectTmdb,
    handleClearTmdb,
  };
}
