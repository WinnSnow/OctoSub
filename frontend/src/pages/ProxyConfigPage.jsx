import React, { useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { PageHeader, StatusBadge } from '../components/ui';
import ProxyConfigForm from '../components/proxy/ProxyConfigForm';
import ProxyHelpPanel from '../components/proxy/ProxyHelpPanel';
import ProxyStatusPanel from '../components/proxy/ProxyStatusPanel';
import { getApiErrorMessage } from '../api/errors';
import { deleteProxyConfig, getProxyConfig, saveProxyConfig, testProxyConfig, updateProxyState } from '../api/proxy';
import { PROXY_DEFAULT_CONFIG, PROXY_EXAMPLE_LINK } from '../config/app';
import { PROXY_MODE_LABELS } from '../config/proxy';
import { parseProxyLink } from '../utils/proxy';

function ProxyConfigPage() {
  const [config, setConfig] = useState(PROXY_DEFAULT_CONFIG);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [hasProxy, setHasProxy] = useState(false);
  const [applyingAction, setApplyingAction] = useState('');
  const [importLink, setImportLink] = useState('');

  useEffect(() => {
    fetchProxyConfig();
  }, []);

  const fetchProxyConfig = async () => {
    try {
      const response = await getProxyConfig();
      if (response.data) {
        setConfig(prev => ({
          ...prev,
          ...response.data,
          enabled: response.data.enabled !== undefined ? response.data.enabled : true,
          mode: response.data.mode || 'auto',
        }));
        setHasProxy(response.data.system_mode === 'proxy');
      } else {
        setHasProxy(false);
      }
    } catch (error) {
      console.error('Error fetching proxy config:', error);
    }
  };

  const applyProxyState = async (payload, successLabel) => {
    setApplyingAction(successLabel);
    const toastId = toast.loading(`正在${successLabel}...`);
    try {
      const response = await updateProxyState(payload);
      if (response.data.config) {
        setConfig(prev => ({ ...prev, ...response.data.config }));
      } else {
        setConfig(prev => ({ ...prev, ...payload }));
      }
      setHasProxy(response.data.system_mode === 'proxy');
      toast.success(response.data.message || `${successLabel}完成`, { id: toastId });
      fetchProxyConfig();
    } catch (error) {
      toast.error(getApiErrorMessage(error, `${successLabel}失败`), { id: toastId });
    } finally {
      setApplyingAction('');
    }
  };

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setConfig(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleImportLink = () => {
    if (!importLink) return;
    const parsed = parseProxyLink(importLink);
    if (parsed) {
      setConfig(prev => ({ ...prev, ...parsed }));
      toast.success(`已解析并填充 ${parsed.protocol.toUpperCase()} 配置`);
      setImportLink('');
    } else {
      toast.error(`无法解析该链接，请检查格式 (例: ${PROXY_EXAMPLE_LINK})`);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    const toastId = toast.loading('正在测试代理连接 (访问 Google)...');
    try {
      const response = await testProxyConfig({
        ...config,
        port: parseInt(config.port, 10),
      });
      toast.success(response.data.message, { id: toastId });
    } catch (error) {
      toast.error(`连接失败: ${getApiErrorMessage(error)}`, { id: toastId });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    const toastId = toast.loading('正在保存并应用代理...');
    try {
      const res = await saveProxyConfig({
        ...config,
        port: parseInt(config.port, 10),
      });
      toast.success(res.data.message || '代理已保存', { id: toastId });
      fetchProxyConfig();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '保存失败'), { id: toastId });
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('确定要移除代理设置吗？Telegram 客户端将直连。')) return;
    setLoading(true);
    const toastId = toast.loading('正在移除代理...');
    try {
      await deleteProxyConfig();
      toast.success('代理已移除', { id: toastId });
      setHasProxy(false);
      setConfig(PROXY_DEFAULT_CONFIG);
    } catch (error) {
      toast.error(getApiErrorMessage(error, '移除失败'), { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  const isBusy = loading || testing || Boolean(applyingAction);
  const proxyFieldsActive = config.enabled && config.mode !== 'direct';
  const statusLabel = hasProxy ? '代理生效中' : (config.enabled ? '当前直连模式' : '代理已停用');
  const statusConfig = {
    ...config,
    modeLabel: config.enabled ? PROXY_MODE_LABELS[config.mode] : '停用代理模块',
  };

  return (
    <div className="fade-in proxy-page">
      <PageHeader
        eyebrow="Network"
        title="代理设置"
        description="配置 Telegram 客户端网络连接，并在直连、自动和强制代理之间切换。"
        meta={<StatusBadge status={hasProxy ? 'connected' : 'skipped'}>{statusLabel}</StatusBadge>}
      />

      <ProxyStatusPanel
        statusLabel={statusLabel}
        config={statusConfig}
        hasProxy={hasProxy}
        onModeChange={applyProxyState}
        isBusy={isBusy}
      />

      <ProxyConfigForm
        config={config}
        hasProxy={hasProxy}
        isBusy={isBusy}
        loading={loading}
        testing={testing}
        proxyFieldsActive={proxyFieldsActive}
        importLink={importLink}
        onChange={handleChange}
        onModeChange={applyProxyState}
        onImportLink={handleImportLink}
        onImportLinkChange={setImportLink}
        onDelete={handleDelete}
        onTest={handleTest}
        onSave={handleSave}
      />

      <ProxyHelpPanel />
    </div>
  );
}

export default ProxyConfigPage;
