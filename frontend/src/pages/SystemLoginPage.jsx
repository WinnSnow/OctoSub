import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { login } from '../api/auth';
import { getApiErrorMessage } from '../api/errors';
import { APP_LOGIN_SUBTITLE, APP_LOGIN_TITLE } from '../config/app';

function SystemLoginPage({ onLogin }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!username || !password) {
      toast.error('请输入用户名和密码');
      return;
    }

    setLoading(true);
    try {
      const response = await login({ username, password });
      toast.success('登录成功');
      onLogin(response.data.user);
    } catch (error) {
      toast.error(getApiErrorMessage(error, '登录失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="system-login-shell">
      <div className="system-login-panel">
        <div className="mb-4">
          <div className="login-kicker">TG Web View</div>
          <h1 className="login-title">{APP_LOGIN_TITLE}</h1>
          <p className="login-subtitle">{APP_LOGIN_SUBTITLE}</p>
        </div>

        <form onSubmit={handleSubmit} className="d-grid gap-3">
          <div>
            <label className="form-label fw-bold small">用户名</label>
            <input
              className="form-control form-control-lg"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </div>
          <div>
            <label className="form-label fw-bold small">密码</label>
            <input
              type="password"
              className="form-control form-control-lg"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              autoFocus
            />
          </div>
          <button className="btn btn-primary btn-lg w-100" disabled={loading}>
            {loading && <span className="spinner-border spinner-border-sm me-2" />}
            登录
          </button>
        </form>
      </div>
    </div>
  );
}

export default SystemLoginPage;
