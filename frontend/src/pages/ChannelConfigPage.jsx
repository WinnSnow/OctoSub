import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { Plus, RefreshCcw, Satellite, Square, Trash2, Wrench } from 'lucide-react';
import { EmptyState, IconButton, PageHeader, Panel, StatusBadge } from '../components/ui';
import { getApiErrorMessage } from '../api/errors';
import { addChannel, deleteChannel, getChannels, retryMissingForChannel, scrape } from '../api/channels';
import { cancelTask, getTask, getTasks } from '../api/tasks';

const CHANNEL_FETCH_TASK_KEY = 'tg-web-view:last-fetch-task-id';
const ACTIVE_FETCH_STATUSES = new Set(['queued', 'running', 'cancel_requested']);

function ChannelConfigPage() {
  const [channels, setChannels] = useState([]);
  const [newChannelUrl, setNewChannelUrl] = useState('');
  const [busyChannel, setBusyChannel] = useState(null);
  const [activeFetchTask, setActiveFetchTask] = useState(null);
  const [stoppingTaskId, setStoppingTaskId] = useState('');

  useEffect(() => {
    fetchChannels();
    restoreFetchTask();
  }, []);

  useEffect(() => {
    if (!activeFetchTask || !ACTIVE_FETCH_STATUSES.has(activeFetchTask.status)) return undefined;
    const timer = window.setInterval(() => {
      refreshFetchTask(activeFetchTask.task_id);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeFetchTask]);

  const fetchChannels = async () => {
    try {
      const response = await getChannels();
      setChannels(response.data);
    } catch (error) {
      console.error('Error fetching channels:', error);
      toast.error('获取频道列表失败。');
    }
  };

  const applyFetchTask = (task) => {
    if (!task?.task_id || task.type !== 'fetch') return;
    setActiveFetchTask(task);
    if (ACTIVE_FETCH_STATUSES.has(task.status)) {
      window.localStorage.setItem(CHANNEL_FETCH_TASK_KEY, task.task_id);
    } else {
      window.localStorage.removeItem(CHANNEL_FETCH_TASK_KEY);
    }
  };

  const refreshFetchTask = async (taskId) => {
    if (!taskId) return;
    try {
      const response = await getTask(taskId);
      applyFetchTask(response.data);
    } catch {
      window.localStorage.removeItem(CHANNEL_FETCH_TASK_KEY);
      setActiveFetchTask(null);
    }
  };

  const restoreFetchTask = async () => {
    const savedTaskId = window.localStorage.getItem(CHANNEL_FETCH_TASK_KEY);
    if (savedTaskId) {
      await refreshFetchTask(savedTaskId);
      return;
    }
    try {
      for (const status of ['queued', 'running', 'cancel_requested']) {
        const response = await getTasks({ status, task_type: 'fetch', page: 1, limit: 5 });
        const task = response.data?.items?.[0];
        if (task) {
          applyFetchTask(task);
          return;
        }
      }
    } catch {
      // Task recovery is opportunistic; channel management remains available.
    }
  };

  const handleAddChannel = async (e) => {
    e.preventDefault();
    if (!newChannelUrl) return;
    try {
      const response = await addChannel({ url: newChannelUrl });
      setChannels([...channels, response.data]);
      setNewChannelUrl('');
      toast.success('频道添加成功!');
    } catch (error) {
      console.error('Error adding channel:', error);
      toast.error(getApiErrorMessage(error, '添加频道失败。'));
    }
  };

  const handleDeleteChannel = async (channelId) => {
    if (!window.confirm('确定删除这个频道吗？本地消息不会自动删除。')) return;
    try {
      await deleteChannel(channelId);
      setChannels(channels.filter(c => c.id !== channelId));
      toast.success('频道已删除。');
    } catch (error) {
      console.error('Error deleting channel:', error);
      toast.error('删除失败。');
    }
  };

  const startChannelTask = async (channelName, request) => {
    setBusyChannel(channelName);
    try {
      const response = await request();
      toast.success(response.data.message || '任务已启动');
      if (response.data?.task_id) {
        await refreshFetchTask(response.data.task_id);
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, '任务启动失败'));
    } finally {
      setBusyChannel(null);
    }
  };

  const handleRefreshChannel = (channelName) => {
    startChannelTask(channelName, () => scrape({ channel_name: channelName }));
  };

  const handleRetryMissing = (channelName) => {
    startChannelTask(channelName, () => retryMissingForChannel(channelName));
  };

  const handleStopFetchTask = async () => {
    if (!activeFetchTask?.task_id) return;
    setStoppingTaskId(activeFetchTask.task_id);
    try {
      await cancelTask(activeFetchTask.task_id);
      toast.success('已请求停止抓取');
      await refreshFetchTask(activeFetchTask.task_id);
    } catch (error) {
      toast.error(getApiErrorMessage(error, '停止抓取失败'));
    } finally {
      setStoppingTaskId('');
    }
  };

  const renderChannelTask = (channelUrl) => {
    if (!activeFetchTask || !ACTIVE_FETCH_STATUSES.has(activeFetchTask.status)) return null;
    if (activeFetchTask.channel !== 'ALL' && activeFetchTask.channel !== channelUrl) return null;
    return (
      <div className="channel-task-row">
        <StatusBadge status={activeFetchTask.status} />
        <span className="small text-muted">
          {activeFetchTask.current || 0}/{activeFetchTask.total || 0}
        </span>
        <IconButton
          icon={Square}
          className="btn-outline-danger btn-sm"
          onClick={handleStopFetchTask}
          disabled={!['queued', 'running'].includes(activeFetchTask.status) || stoppingTaskId === activeFetchTask.task_id}
        >
          {stoppingTaskId === activeFetchTask.task_id ? '停止中...' : '停止'}
        </IconButton>
      </div>
    );
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Channels"
        title="频道配置"
        description="管理需要监控和抓取的 Telegram 频道，并对单个频道执行刷新或补链。"
        meta={<span className="status-badge muted">{channels.length} 个已订阅</span>}
      />

      <div className="row g-4">
        <div className="col-xl-5">
            <Panel>
                    <h5 className="mb-3 text-primary d-flex align-items-center gap-2">
                        <Plus size={18} /> 新增频道
                    </h5>
                    <form onSubmit={handleAddChannel} className="row g-3 align-items-end">
                        <div className="col-12">
                            <label htmlFor="channelUrl" className="form-label text-muted small fw-bold">频道链接 / 用户名</label>
                            <div className="input-group">
                                <span className="input-group-text border-end-0">@</span>
                                <input
                                    type="text"
                                    className="form-control border-start-0 ps-0"
                                    id="channelUrl"
                                    value={newChannelUrl}
                                    onChange={(e) => setNewChannelUrl(e.target.value)}
                                    placeholder="例如: google_news 或 https://t.me/..."
                                />
                            </div>
                        </div>
                        <div className="col-12 d-grid">
                            <button type="submit" className="btn btn-primary" disabled={!newChannelUrl}>
                                <Plus size={16} /> 添加订阅
                            </button>
                        </div>
                    </form>
                    <div className="form-text mt-2 text-muted small">
                        支持输入完整链接 (https://t.me/...) 或直接输入频道用户名 (例如: BBCNews)。
                    </div>
            </Panel>
        </div>

        <div className="col-xl-7">
            <Panel compact>
                <div className="px-3 py-3 border-bottom">
                    <h5 className="mb-0 text-dark d-flex align-items-center gap-2">
                        <Satellite size={18} /> 已保存频道
                    </h5>
                </div>
                    {channels.length === 0 ? (
                        <div className="p-3">
                          <EmptyState icon={Satellite} title="暂无订阅频道" description="在左侧添加频道后，这里会显示刷新、补链和删除操作。" />
                        </div>
                    ) : (
                        <div className="list-group list-group-flush">
                            {channels.map((channel) => (
                            <div key={channel.id} className="list-group-item channel-list-item d-flex justify-content-between align-items-center py-3 px-3 border-bottom">
                                <div className="d-flex align-items-center min-w-0">
                                    <div className="account-avatar me-3">
                                        <Satellite size={16} />
                                    </div>
                                    <div className="min-w-0">
                                      <div className="fw-medium text-break">{channel.url}</div>
                                      {renderChannelTask(channel.url)}
                                    </div>
                                </div>
                                <div className="channel-list-actions d-flex gap-2 flex-wrap justify-content-end">
                                    <IconButton
                                        icon={RefreshCcw}
                                        className="btn-outline-primary btn-sm"
                                        onClick={() => handleRefreshChannel(channel.url)}
                                        disabled={busyChannel === channel.url}
                                    >
                                        刷新
                                    </IconButton>
                                    <IconButton
                                        icon={Wrench}
                                        className="btn-outline-secondary btn-sm"
                                        onClick={() => handleRetryMissing(channel.url)}
                                        disabled={busyChannel === channel.url}
                                    >
                                        补链
                                    </IconButton>
                                    <IconButton
                                        icon={Trash2}
                                        className="btn-outline-danger btn-sm"
                                        onClick={() => handleDeleteChannel(channel.id)}
                                    >
                                        删除
                                    </IconButton>
                                </div>
                            </div>
                            ))}
                        </div>
                    )}
            </Panel>
        </div>
      </div>
    </div>
  );
}

export default ChannelConfigPage;
