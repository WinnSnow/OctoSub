import React from 'react';
import { KeyRound, Lock, Phone } from 'lucide-react';

function LoadingPrefix({ loading }) {
  return loading ? <span className="spinner-border spinner-border-sm me-2" /> : null;
}

function TelegramLoginSteps({
  step,
  loading,
  phone,
  code,
  password,
  onPhoneChange,
  onCodeChange,
  onPasswordChange,
  onSendCode,
  onVerifyCode,
  onVerifyPassword,
  onBackToPhone,
}) {
  return (
    <div className="login-form mt-4">
      {step === 'phone' && (
        <div className="mb-3">
          <label className="form-label fw-bold">手机号</label>
          <div className="input-group">
            <span className="input-group-text"><Phone size={16} /></span>
            <input
              type="text"
              className="form-control"
              placeholder="+86138..."
              value={phone}
              onChange={(event) => onPhoneChange(event.target.value)}
            />
          </div>
          <div className="form-text mt-2">请输入完整的国际格式手机号（带 + 号）。</div>
          <button className="btn btn-primary w-100 mt-3 py-2" onClick={onSendCode} disabled={loading}>
            <LoadingPrefix loading={loading} />
            发送验证码
          </button>
        </div>
      )}

      {step === 'code' && (
        <div className="mb-3">
          <label className="form-label fw-bold">验证码</label>
          <div className="input-group">
            <span className="input-group-text"><KeyRound size={16} /></span>
            <input
              type="text"
              className="form-control"
              placeholder="5 位数字"
              value={code}
              onChange={(event) => onCodeChange(event.target.value)}
            />
          </div>
          <button className="btn btn-primary w-100 mt-3 py-2" onClick={onVerifyCode} disabled={loading}>
            <LoadingPrefix loading={loading} />
            验证并登录
          </button>
          <button className="btn btn-link btn-sm w-100 mt-2 text-muted" onClick={onBackToPhone}>
            返回修改手机号
          </button>
        </div>
      )}

      {step === 'password' && (
        <div className="mb-3">
          <label className="form-label fw-bold">两步验证密码 (2FA)</label>
          <div className="input-group">
            <span className="input-group-text"><Lock size={16} /></span>
            <input
              type="password"
              className="form-control"
              placeholder="请输入您的 2FA 密码"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
            />
          </div>
          <button className="btn btn-primary w-100 mt-3 py-2" onClick={onVerifyPassword} disabled={loading}>
            <LoadingPrefix loading={loading} />
            确认
          </button>
        </div>
      )}
    </div>
  );
}

export default TelegramLoginSteps;
