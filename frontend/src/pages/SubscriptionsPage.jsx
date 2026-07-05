import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { Bell, CheckCircle2, Plus, RefreshCcw } from 'lucide-react';
import SubscriptionHelpPanel from '../components/subscriptions/SubscriptionHelpPanel';
import SubscriptionForm from '../components/subscriptions/SubscriptionForm';
import SubscriptionSchedulerStatus from '../components/subscriptions/SubscriptionSchedulerStatus';
import SubscriptionsTable from '../components/subscriptions/SubscriptionsTable';
import TaskProgressStrip from '../components/home/TaskProgressStrip';
import { EmptyState, IconButton, LoadingState, PageHeader } from '../components/ui';
import { getApiErrorMessage } from '../api/errors';
import {
  deleteSubscription,
  updateSubscriptionStatus,
} from '../api/subscriptions';
import {
  SUBSCRIPTION_VIEW_FILTERS,
  getSubscriptionStatus,
} from '../utils/subscriptions';
import { useSubscriptionFormController } from '../hooks/useSubscriptionFormController';
import { useSubscriptionsData } from '../hooks/useSubscriptionsData';
import { useSubscriptionTaskController } from '../hooks/useSubscriptionTaskController';

function SubscriptionsPage() {
  const [viewFilter, setViewFilter] = useState('active');
  const {
    subscriptions,
    loading,
    scheduler,
    refreshSubscriptions,
  } = useSubscriptionsData();
  const {
    checking,
    checkingId,
    activeTask,
    cancellingTaskId,
    handleManualCheck,
    handleRefreshLifecycle,
    handleSingleCheck,
    handleCancelTask,
    startLifecycleRefresh,
  } = useSubscriptionTaskController({ refreshSubscriptions });
  const formController = useSubscriptionFormController({
    refreshSubscriptions,
    startLifecycleRefresh,
  });

  const handleDelete = async (id) => {
    if (!window.confirm('确定删除此订阅吗？')) return;

    try {
      await deleteSubscription(id);
      toast.success('订阅已删除');
      refreshSubscriptions();
    } catch (error) {
      toast.error('删除失败');
    }
  };

  const handleStatusChange = async (sub, status) => {
    const label = status === 'active' ? '恢复订阅' : (status === 'paused' ? '停用订阅' : '标记完成');
    if (status === 'completed' && !window.confirm(`确定将「${sub.keyword}」标记为已完成吗？完成后不会参与定时检查。`)) {
      return;
    }

    try {
      await updateSubscriptionStatus(sub.id, {
        status,
        enabled: status === 'active',
      });
      toast.success(`${label}完成`);
      refreshSubscriptions();
    } catch (error) {
      toast.error(getApiErrorMessage(error, `${label}失败`));
    }
  };

  const visibleSubscriptions = subscriptions.filter((sub) => {
    const status = getSubscriptionStatus(sub);
    if (viewFilter === 'all') return true;
    if (viewFilter === 'completed') return status === 'completed';
    return status !== 'completed';
  });

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Subscriptions"
        title="订阅管理"
        description="用 TMDB 和 Jellyfin 跟踪入库进度，自动只检查下一集，历史缺失由你手动处理。"
        actions={(
          <>
            <IconButton icon={RefreshCcw} className="btn-outline-secondary" onClick={handleRefreshLifecycle} disabled={checking}>
              {checking ? '同步中...' : '同步状态'}
            </IconButton>
            <IconButton icon={RefreshCcw} className="btn-outline-primary" onClick={handleManualCheck} disabled={checking}>
              {checking ? '检查中...' : '检查下一集'}
            </IconButton>
            <IconButton icon={Plus} className="btn-primary" onClick={() => formController.setShowForm(true)}>
              新建订阅
            </IconButton>
          </>
        )}
      />

      <div className="segmented-control compact mb-3">
        {SUBSCRIPTION_VIEW_FILTERS.map(({ value, label }) => (
          <button key={value} className={viewFilter === value ? 'active' : ''} onClick={() => setViewFilter(value)}>
            {label}
          </button>
        ))}
      </div>

      <SubscriptionSchedulerStatus scheduler={scheduler} />
      <TaskProgressStrip
        task={activeTask}
        onCancel={handleCancelTask}
        cancelling={Boolean(cancellingTaskId)}
      />

      {formController.showForm && (
        <SubscriptionForm
          editingId={formController.editingId}
          formData={formController.formData}
          selectedTmdb={formController.selectedTmdb}
          tmdbQuery={formController.tmdbQuery}
          tmdbResults={formController.tmdbResults}
          tmdbSearching={formController.tmdbSearching}
          tmdbTvDetail={formController.tmdbTvDetail}
          tmdbDetailLoading={formController.tmdbDetailLoading}
          onSubmit={formController.handleSubmit}
          onCancel={formController.handleCancel}
          onFormChange={formController.handleFormChange}
          onTmdbQueryChange={formController.setTmdbQuery}
          onTmdbSearch={formController.handleTmdbSearch}
          onSelectTmdb={formController.handleSelectTmdb}
          onClearTmdb={formController.handleClearTmdb}
        />
      )}

      {loading && (
        <LoadingState label="正在加载订阅..." />
      )}

      {!loading && subscriptions.length === 0 && (
        <EmptyState
          icon={Bell}
          title="还没有订阅"
          description="创建订阅后，系统会按计划检查新资源并记录处理结果。"
          actions={<button className="btn btn-primary" onClick={() => formController.setShowForm(true)}><Plus size={16} /> 新建订阅</button>}
        />
      )}

      {!loading && subscriptions.length > 0 && visibleSubscriptions.length === 0 && (
        <EmptyState
          icon={CheckCircle2}
          title="没有匹配的订阅"
          description={viewFilter === 'completed' ? '当前没有已完成订阅。' : '当前筛选条件下没有订阅。'}
        />
      )}

      {!loading && visibleSubscriptions.length > 0 && (
        <SubscriptionsTable
          subscriptions={visibleSubscriptions}
          checkingId={checkingId}
          onEdit={formController.handleEdit}
          onStatusChange={handleStatusChange}
          onSingleCheck={handleSingleCheck}
          onDelete={handleDelete}
        />
      )}

      <SubscriptionHelpPanel />
    </div>
  );
}

export default SubscriptionsPage;
