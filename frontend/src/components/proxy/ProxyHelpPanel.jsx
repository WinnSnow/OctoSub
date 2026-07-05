import React from 'react';
import { Panel } from '../ui';

function ProxyHelpPanel() {
  return (
    <Panel className="mt-4">
      <h6 className="text-secondary">说明：</h6>
      <ul className="list-unstyled ps-2">
        <li className="mb-1">• <b>SOCKS 快速导入</b>：当选择 SOCKS 协议时，可以粘贴完整链接一键填充。</li>
        <li className="mb-1">• <b>生效时间</b>：保存配置后，后端服务会自动重启客户端会话，这可能需要几秒钟。</li>
        <li className="mb-1">• <b>连通性</b>：测试通过仅代表服务器可以连接到公网，不代表一定能连接到 Telegram 服务器（取决于代理质量）。</li>
      </ul>
    </Panel>
  );
}

export default ProxyHelpPanel;
