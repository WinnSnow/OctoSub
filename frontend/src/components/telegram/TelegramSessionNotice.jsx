import React from 'react';

function TelegramSessionNotice() {
  return (
    <div className="alert alert-info border-0 shadow-sm">
      <h6 className="alert-heading">提示</h6>
      <p className="mb-0 small">
        如果您迁移了服务器，Telegram 可能会提示“多个 IP 登录”。在此处重新登录可以刷新服务器端的 Session 文件，从而解决该问题。
      </p>
    </div>
  );
}

export default TelegramSessionNotice;
