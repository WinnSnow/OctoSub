import React from 'react';
import { Network } from 'lucide-react';
import { Panel } from '../ui';

function ProxyStatusPanel({ statusLabel, config, hasProxy, onModeChange, isBusy }) {
  return (
    <Panel className="proxy-status-panel mb-3">
      <div className="proxy-status-copy">
        <div className="proxy-status-icon">
          <Network size={20} />
        </div>
        <div>
          <h5>{statusLabel}</h5>
          <p>
            当前模式：{config.enabled ? config.modeLabel : '停用代理模块'}
            {hasProxy && ` · ${config.protocol.toUpperCase()} ${config.host}:${config.port}`}
          </p>
        </div>
      </div>
      <div className="proxy-quick-actions">
        <button
          className={`proxy-mode-card ${!config.enabled ? 'active' : ''}`}
          onClick={() => onModeChange({ enabled: false }, '停用代理')}
          disabled={isBusy}
        >
          <strong>停用</strong>
          <span>保留配置但不参与连接</span>
        </button>
        <button
          className={`proxy-mode-card ${config.enabled && config.mode === 'direct' ? 'active' : ''}`}
          onClick={() => onModeChange({ enabled: true, mode: 'direct' }, '切换直连')}
          disabled={isBusy}
        >
          <strong>直连</strong>
          <span>不使用任何代理</span>
        </button>
        <button
          className={`proxy-mode-card ${config.enabled && config.mode === 'auto' ? 'active' : ''}`}
          onClick={() => onModeChange({ enabled: true, mode: 'auto' }, '切换自动模式')}
          disabled={isBusy}
        >
          <strong>自动</strong>
          <span>直连失败再走代理</span>
        </button>
        <button
          className={`proxy-mode-card ${config.enabled && config.mode === 'manual' ? 'active' : ''}`}
          onClick={() => onModeChange({ enabled: true, mode: 'manual' }, '启用强制代理')}
          disabled={isBusy || !config.host}
        >
          <strong>强制代理</strong>
          <span>全部请求走代理</span>
        </button>
      </div>
    </Panel>
  );
}

export default ProxyStatusPanel;
