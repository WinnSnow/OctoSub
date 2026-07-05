import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { CheckCircle2, Clapperboard, Eye, EyeOff, RefreshCcw, Save, Server, XCircle } from 'lucide-react';
import { IconButton, LoadingState, PageHeader, Panel, StatusBadge } from '../components/ui';
import { getApiErrorMessage } from '../api/errors';
import {
  getJellyfinConfig,
  getJellyfinLibraryIndex,
  getJellyfinStatus,
  saveJellyfinConfig,
  syncJellyfinLibrary,
  testJellyfinConnection,
} from '../api/jellyfin';
import { getTask } from '../api/tasks';
import { JELLYFIN_ENV_EXAMPLE, JELLYFIN_EXAMPLE_URL } from '../config/app';

function JellyfinConfigPage() {
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState({ url: '', api_key: '' });
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showApiKey, setShowApiKey] = useState(false);
  const [indexSummary, setIndexSummary] = useState(null);
  const [syncingIndex, setSyncingIndex] = useState(false);
  const [indexSyncTask, setIndexSyncTask] = useState(null);

  useEffect(() => {
    fetchStatus();
    fetchConfig();
    fetchIndexSummary();
  }, []);

  useEffect(() => {
    if (!indexSyncTask?.task_id || !['running', 'cancel_requested'].includes(indexSyncTask.status)) {
      return undefined;
    }
    const intervalId = setInterval(async () => {
      try {
        const response = await getTask(indexSyncTask.task_id);
        const task = response.data;
        setIndexSyncTask(task);
        if (['completed', 'failed', 'cancelled'].includes(task.status)) {
          clearInterval(intervalId);
          setSyncingIndex(false);
          fetchIndexSummary();
          if (task.status === 'completed') {
            toast.success(task.message || 'Jellyfin 媒体库索引同步完成');
          } else {
            toast.error(task.message || 'Jellyfin 媒体库索引同步失败');
          }
        }
      } catch (error) {
        clearInterval(intervalId);
        setSyncingIndex(false);
      }
    }, 1500);
    return () => clearInterval(intervalId);
  }, [indexSyncTask]);

  const fetchStatus = async () => {
    try {
      const response = await getJellyfinStatus();
      setStatus(response.data);
    } catch (error) {
      toast.error('获取 Jellyfin 状态失败');
    }
  };

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await getJellyfinConfig();
      setConfig({
        url: response.data.url || '',
        api_key: response.data.api_key || ''
      });
    } catch (error) {
      toast.error('获取配置失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchIndexSummary = async () => {
    try {
      const response = await getJellyfinLibraryIndex();
      setIndexSummary(response.data);
    } catch (error) {
      setIndexSummary(null);
    }
  };

  const handleSave = async () => {
    if (!config.url.trim() || !config.api_key.trim()) {
      toast.error('请填写完整的配置信息');
      return;
    }

    setSaving(true);
    try {
      const response = await saveJellyfinConfig(config);
      toast.success(response.data.message);
      fetchStatus();
      fetchIndexSummary();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!config.url.trim() || !config.api_key.trim()) {
      toast.error('请先保存配置');
      return;
    }

    setTesting(true);
    try {
      await testJellyfinConnection(config);
      toast.success('连接成功！');
      setStatus({ ...status, connected: true });

    } catch (error) {
      toast.error(getApiErrorMessage(error, '连接失败'));
      setStatus({ ...status, connected: false });
    } finally {
      setTesting(false);
    }
  };

  const handleSyncIndex = async () => {
    setSyncingIndex(true);
    try {
      const response = await syncJellyfinLibrary();
      if (response.data?.task_id) {
        setIndexSyncTask({
          task_id: response.data.task_id,
          status: 'running',
          message: response.data.message,
        });
      } else {
        setSyncingIndex(false);
      }
      toast.success(response.data.message || 'Jellyfin 媒体库同步任务已启动');
      fetchIndexSummary();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '同步媒体库索引失败'));
      setSyncingIndex(false);
    }
  };

  if (loading) {
    return (
      <LoadingState label="正在加载 Jellyfin 配置..." />
    );
  }

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Jellyfin"
        title="Jellyfin 配置"
        description="连接媒体库后，订阅系统会自动识别已有影视资源，减少重复转存。"
        meta={<StatusBadge status={status?.connected ? 'connected' : 'disconnected'}>{status?.connected ? '已连接' : '未连接'}</StatusBadge>}
      />

      <div className="row">
        <div className="col-lg-8">
          <Panel className="mb-4">
              <h5 className="card-title">Jellyfin 服务器配置</h5>

              <div className="mb-3">
                <label className="form-label">服务器地址 *</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder={JELLYFIN_EXAMPLE_URL}
                  value={config.url}
                  onChange={(e) => setConfig({ ...config, url: e.target.value })}
                />
                <small className="text-muted">Jellyfin 服务器的完整地址（包括端口）</small>
              </div>

              <div className="mb-3">
                <label className="form-label">API 密钥 *</label>
                <div className="input-group">
                  <input
                    type={showApiKey ? "text" : "password"}
                    className="form-control"
                    placeholder="输入 API Key"
                    value={config.api_key}
                    onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                  />
                  <button
                    className="btn btn-outline-secondary"
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                  >
                    {showApiKey ? <><EyeOff size={16} /> 隐藏</> : <><Eye size={16} /> 显示</>}
                  </button>
                </div>
                <small className="text-muted">在 Jellyfin 管理后台 → API 密钥 中生成</small>
              </div>

              <div className="config-form-actions d-flex gap-2">
                <IconButton
                  icon={Save}
                  className="btn-primary"
                  onClick={handleSave}
                  disabled={saving || !config.url.trim() || !config.api_key.trim()}
                >
                  {saving ? '保存中...' : '保存配置'}
                </IconButton>
                <IconButton
                  icon={Server}
                  className="btn-outline-primary"
                  onClick={handleTest}
                  disabled={testing || !config.url.trim() || !config.api_key.trim()}
                >
                  {testing ? '测试中...' : '测试连接'}
                </IconButton>
                <IconButton icon={RefreshCcw} className="btn-outline-secondary" onClick={() => { fetchStatus(); fetchConfig(); }}>
                  刷新状态
                </IconButton>
              </div>
          </Panel>

          <Panel className="mb-4">
              <h5 className="card-title">媒体库索引</h5>
              <p className="text-muted mb-3">
                搜索入库状态会优先使用本地索引，减少逐条查询 Jellyfin。
              </p>
              <div className="row g-2 mb-3">
                <div className="col-6 col-md-3">
                  <div className="small text-muted">总项目</div>
                  <div className="fw-semibold">{indexSummary?.total || 0}</div>
                </div>
                <div className="col-6 col-md-3">
                  <div className="small text-muted">电影</div>
                  <div className="fw-semibold">{indexSummary?.movies || 0}</div>
                </div>
                <div className="col-6 col-md-3">
                  <div className="small text-muted">剧集</div>
                  <div className="fw-semibold">{indexSummary?.series || 0}</div>
                </div>
                <div className="col-6 col-md-3">
                  <div className="small text-muted">分集</div>
                  <div className="fw-semibold">{indexSummary?.episodes || 0}</div>
                </div>
              </div>
              <div className="d-flex align-items-center gap-2 flex-wrap">
                <IconButton
                  icon={RefreshCcw}
                  className="btn-outline-primary"
                  onClick={handleSyncIndex}
                  disabled={syncingIndex || !status?.connected}
                >
                  {syncingIndex ? '启动中...' : '同步媒体库索引'}
                </IconButton>
                <button className="btn btn-outline-secondary btn-sm" type="button" onClick={fetchIndexSummary}>
                  刷新索引状态
                </button>
                <span className="small text-muted">
                  {indexSyncTask?.status === 'running'
                    ? (indexSyncTask.message || '同步任务运行中')
                    : (indexSummary?.last_sync_at ? `上次同步：${indexSummary.last_sync_at}` : '尚未同步')}
                </span>
              </div>
          </Panel>

          <Panel className="mb-4">
              <h5 className="card-title">连接状态</h5>

              <div className="d-flex align-items-center mb-3">
                <div className="me-3">
                  {status?.connected ? (
                    <CheckCircle2 className="text-success" size={44} />
                  ) : (
                    <XCircle className="text-danger" size={44} />
                  )}
                </div>
                <div>
                  <h4 className="mb-1">
                    {status?.connected ? '已连接' : '未连接'}
                  </h4>
                  <p className="text-muted mb-0">{status?.message}</p>
                </div>
              </div>

              {status?.url && (
                <div className="mb-3">
                  <label className="form-label fw-bold">当前服务器</label>
                  <p className="mb-0">
                    <code>{status.url}</code>
                  </p>
                </div>
              )}
          </Panel>

          <Panel>
              <h5 className="card-title">功能说明</h5>
              <ul className="mb-0">
                <li className="mb-2">
                  <strong>订阅去重</strong>：订阅系统会自动检查 Jellyfin 媒体库，避免重复下载已有的剧集和电影
                </li>
                <li className="mb-2">
                  <strong>剧集检查</strong>：对于剧集类订阅，系统会检查指定季集是否已存在
                </li>
                <li className="mb-2">
                  <strong>电影检查</strong>：对于电影类订阅，系统会根据名称和年份判断是否已存在
                </li>
                <li>
                  <strong>可选配置</strong>：如果不配置 Jellyfin，订阅系统仍可正常运行，但不会进行媒体库检查
                </li>
              </ul>
          </Panel>
        </div>

        <div className="col-lg-4">
          <Panel className="bg-light">
              <h6 className="card-title d-flex align-items-center gap-2"><Clapperboard size={16} /> 配置指南</h6>

              <div className="mb-3">
                <strong>1. 获取 API 密钥</strong>
                <ol className="small mb-0 mt-2">
                  <li>登录 Jellyfin 管理后台</li>
                  <li>进入 <code>控制台 → API 密钥</code></li>
                  <li>点击"新建 API 密钥"</li>
                  <li>输入应用名称（如"TG-Web-Viewer"）</li>
                  <li>复制生成的密钥</li>
                </ol>
              </div>

              <div className="mb-3">
                <strong>2. 配置环境变量</strong>
                <p className="small mb-2 mt-2">
                  编辑后端目录下的 <code>.env</code> 文件：
                </p>
                <pre className="bg-white p-2 rounded small mb-0"><code>{JELLYFIN_ENV_EXAMPLE}</code></pre>
              </div>

              <div>
                <strong>3. 重启服务</strong>
                <pre className="bg-white p-2 rounded small mb-0 mt-2"><code>{`cd backend
uvicorn main:app --reload`}</code></pre>
              </div>
          </Panel>

          <Panel className="mt-3">
              <h6 className="card-title">状态指标</h6>
              <table className="table table-sm mb-0">
                <tbody>
                  <tr>
                    <td>已启用</td>
                    <td className="text-end">
                      <span className={`badge ${status?.enabled ? 'bg-success' : 'bg-secondary'}`}>
                        {status?.enabled ? '是' : '否'}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>已配置</td>
                    <td className="text-end">
                      <span className={`badge ${status?.configured ? 'bg-success' : 'bg-warning'}`}>
                        {status?.configured ? '是' : '否'}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>连接状态</td>
                    <td className="text-end">
                      <span className={`badge ${status?.connected ? 'bg-success' : 'bg-danger'}`}>
                        {status?.connected ? '正常' : '异常'}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
          </Panel>
        </div>
      </div>
    </div>
  );
}

export default JellyfinConfigPage;
