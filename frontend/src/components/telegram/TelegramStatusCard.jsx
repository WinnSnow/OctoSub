import React from 'react';
import { Lock, RotateCcw, UserRound } from 'lucide-react';

import { IconButton, Panel } from '../ui';

function TelegramStatusCard({ status, onLogout, onResetSession }) {
  return (
    <Panel className="mb-4">
      <div className="d-flex align-items-center mb-4">
        <div className={`rounded-circle p-3 me-3 ${status.is_authorized ? 'bg-success-subtle text-success' : 'bg-secondary-subtle text-secondary'}`}>
          {status.is_authorized ? <UserRound size={28} /> : <Lock size={28} />}
        </div>
        <div>
          <h5 className="mb-0">{status.is_authorized ? '已登录' : '未登录'}</h5>
          <p className="text-muted mb-0 small">
            {status.is_authorized ? `当前账号: ${status.user}` : '请通过下方流程进行认证'}
          </p>
        </div>
        {status.is_authorized ? (
          <button className="btn btn-outline-danger btn-sm ms-auto" onClick={onLogout}>
            退出
          </button>
        ) : (
          <IconButton icon={RotateCcw} className="btn-outline-warning btn-sm ms-auto" onClick={onResetSession} title="强制重置本地 Session">
            重置会话
          </IconButton>
        )}
      </div>
    </Panel>
  );
}

export default TelegramStatusCard;
