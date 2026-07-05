import React from 'react';
import { Bolt, Home, KeyRound, Network, Save, Trash2, User } from 'lucide-react';

import { PROXY_EXAMPLE_LINK } from '../../config/app';
import { IconButton, Panel } from '../ui';

function ProxyConfigForm({
  config,
  hasProxy,
  isBusy,
  loading,
  testing,
  proxyFieldsActive,
  importLink,
  onChange,
  onModeChange,
  onImportLink,
  onImportLinkChange,
  onDelete,
  onTest,
  onSave,
}) {
  return (
    <Panel>
      <h5 className="mb-3 text-primary d-flex align-items-center gap-2"><Network size={18} /> 代理参数</h5>

      {(config.protocol === 'socks5' || config.protocol === 'socks4') && (
        <div className="proxy-import-box mb-4">
          <label className="form-label fw-bold text-secondary small">
            SOCKS 链接快速导入
          </label>
          <div className="input-group">
            <input
              type="text"
              className="form-control form-control-sm"
              placeholder={`例如: ${PROXY_EXAMPLE_LINK}`}
              value={importLink}
              onChange={(event) => onImportLinkChange(event.target.value)}
            />
            <button
              className="btn btn-outline-secondary btn-sm"
              type="button"
              onClick={onImportLink}
              disabled={!importLink}
            >
              解析并填充
            </button>
          </div>
          <div className="form-text small">支持 socks4:// 或 socks5:// 格式，自动识别账号密码。</div>
        </div>
      )}

      <div className="row g-4">
        <div className="col-md-12">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <label className="form-label fw-bold mb-0">连接模式</label>
            <div className="form-check form-switch">
              <input
                className="form-check-input"
                type="checkbox"
                name="enabled"
                id="proxyEnabled"
                checked={config.enabled}
                onChange={(event) => onModeChange(
                  { enabled: event.target.checked },
                  event.target.checked ? '启用代理模块' : '停用代理模块',
                )}
                disabled={isBusy}
              />
              <label className="form-check-label small fw-bold" htmlFor="proxyEnabled">
                {config.enabled ? '已启用代理模块' : '已禁用代理模块'}
              </label>
            </div>
          </div>
          <div className="btn-group w-100" role="group">
            <input
              type="radio"
              className="btn-check"
              name="mode"
              id="mode-direct"
              value="direct"
              checked={config.mode === 'direct'}
              onChange={() => onModeChange({ enabled: true, mode: 'direct' }, '切换直连')}
              disabled={isBusy}
            />
            <label className="btn btn-outline-primary" htmlFor="mode-direct">强制直连</label>

            <input
              type="radio"
              className="btn-check"
              name="mode"
              id="mode-auto"
              value="auto"
              checked={config.mode === 'auto'}
              onChange={() => onModeChange({ enabled: true, mode: 'auto' }, '切换自动模式')}
              disabled={isBusy}
            />
            <label className="btn btn-outline-primary" htmlFor="mode-auto">智能自动</label>

            <input
              type="radio"
              className="btn-check"
              name="mode"
              id="mode-manual"
              value="manual"
              checked={config.mode === 'manual'}
              onChange={() => onModeChange({ enabled: true, mode: 'manual' }, '启用强制代理')}
              disabled={isBusy || !config.host}
            />
            <label className="btn btn-outline-primary" htmlFor="mode-manual">强制代理</label>
          </div>
          <div className="form-text mt-2 small">
            {config.mode === 'direct' && '直连模式：不使用任何代理设置。'}
            {config.mode === 'auto' && '自动模式：优先直连，若不可用则自动尝试代理。'}
            {config.mode === 'manual' && '代理模式：强制所有流量通过下方配置的代理。'}
          </div>
        </div>

        <div className="col-12"><hr className="my-2 text-muted opacity-25" /></div>

        <div className="col-md-12" style={{ opacity: config.enabled ? 1 : 0.55, pointerEvents: config.enabled ? 'auto' : 'none' }}>
          <label className="form-label fw-bold">代理协议</label>
          <select className="form-select" name="protocol" value={config.protocol} onChange={onChange}>
            <option value="socks5">SOCKS5 (推荐)</option>
            <option value="socks4">SOCKS4</option>
            <option value="http">HTTP</option>
          </select>
        </div>

        <div className="col-md-8" style={{ opacity: proxyFieldsActive ? 1 : 0.55, pointerEvents: proxyFieldsActive ? 'auto' : 'none' }}>
          <label className="form-label fw-bold">服务器地址 (Host)</label>
          <div className="input-group">
            <span className="input-group-text border-end-0"><Home size={16} /></span>
            <input
              type="text"
              className="form-control border-start-0 ps-0"
              name="host"
              value={config.host}
              onChange={onChange}
              placeholder="127.0.0.1"
            />
          </div>
        </div>
        <div className="col-md-4" style={{ opacity: proxyFieldsActive ? 1 : 0.55, pointerEvents: proxyFieldsActive ? 'auto' : 'none' }}>
          <label className="form-label fw-bold">端口 (Port)</label>
          <div className="input-group">
            <span className="input-group-text border-end-0">#</span>
            <input
              type="number"
              className="form-control border-start-0 ps-0"
              name="port"
              value={config.port}
              onChange={onChange}
              placeholder="1080"
            />
          </div>
        </div>

        <div className="col-12"><hr className="my-2 text-muted opacity-25" /></div>

        <div className="col-md-6" style={{ opacity: proxyFieldsActive ? 1 : 0.55, pointerEvents: proxyFieldsActive ? 'auto' : 'none' }}>
          <label className="form-label fw-bold">用户名 <small className="text-muted fw-normal">(可选)</small></label>
          <div className="input-group">
            <span className="input-group-text border-end-0"><User size={16} /></span>
            <input
              type="text"
              className="form-control border-start-0 ps-0"
              name="username"
              value={config.username || ''}
              onChange={onChange}
              autoComplete="off"
              placeholder="Username"
            />
          </div>
        </div>
        <div className="col-md-6" style={{ opacity: proxyFieldsActive ? 1 : 0.55, pointerEvents: proxyFieldsActive ? 'auto' : 'none' }}>
          <label className="form-label fw-bold">密码 <small className="text-muted fw-normal">(可选)</small></label>
          <div className="input-group">
            <span className="input-group-text border-end-0"><KeyRound size={16} /></span>
            <input
              type="password"
              className="form-control border-start-0 ps-0"
              name="password"
              value={config.password || ''}
              onChange={onChange}
              autoComplete="new-password"
              placeholder="Password"
            />
          </div>
        </div>
      </div>

      <div className="proxy-form-footer">
        <div className="d-flex justify-content-between align-items-center">
          <div>
            {(hasProxy || config.host) && (
              <IconButton icon={Trash2} className="btn-outline-danger btn-sm" onClick={onDelete} disabled={isBusy}>
                清空配置
              </IconButton>
            )}
          </div>
          <div className="d-flex gap-2">
            <IconButton icon={Bolt} className="btn-info" onClick={onTest} disabled={isBusy || !config.host}>
              {testing ? '测试中...' : '测试连通性'}
            </IconButton>
            <IconButton icon={Save} className="btn-primary px-4" onClick={onSave} disabled={isBusy || !config.host}>
              {loading ? '保存中...' : '保存并应用'}
            </IconButton>
          </div>
        </div>
      </div>
    </Panel>
  );
}

export default ProxyConfigForm;
