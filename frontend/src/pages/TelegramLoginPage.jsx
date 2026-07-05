import React, { useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { PageHeader, Panel, StatusBadge } from '../components/ui';
import TelegramLoginSteps from '../components/telegram/TelegramLoginSteps';
import TelegramSessionNotice from '../components/telegram/TelegramSessionNotice';
import TelegramStatusCard from '../components/telegram/TelegramStatusCard';
import { getApiErrorMessage } from '../api/errors';
import {
  getTelegramStatus,
  logoutTelegram,
  resetTelegramSession,
  sendTelegramCode,
  verifyTelegramCode,
  verifyTelegramPassword,
} from '../api/telegram';

function TelegramLoginPage() {
  const [status, setStatus] = useState({ is_connected: false, is_authorized: false, user: null });
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [phoneCodeHash, setPhoneCodeHash] = useState('');
  const [step, setStep] = useState('phone');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await getTelegramStatus();
      setStatus(res.data);
    } catch (error) {
      console.error('Failed to fetch telegram status', error);
    }
  };

  const handleSendCode = async () => {
    if (!phone) return toast.error('请输入手机号');
    setLoading(true);
    try {
      const res = await sendTelegramCode({ phone });
      setPhoneCodeHash(res.data.phone_code_hash);
      setStep('code');
      toast.success('验证码已发送');
    } catch (error) {
      toast.error(getApiErrorMessage(error, '发送失败'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!code) return toast.error('请输入验证码');
    setLoading(true);
    try {
      const res = await verifyTelegramCode({
        phone,
        code,
        phone_code_hash: phoneCodeHash,
      });
      if (res.data.status === 'success') {
        toast.success('登录成功');
        fetchStatus();
        setStep('phone');
      } else if (res.data.status === 'password_needed') {
        setStep('password');
        toast.success('请输入两步验证密码');
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, '验证失败'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyPassword = async () => {
    if (!password) return toast.error('请输入密码');
    setLoading(true);
    try {
      await verifyTelegramPassword({ password });
      toast.success('登录成功');
      fetchStatus();
      setStep('phone');
    } catch (error) {
      toast.error(getApiErrorMessage(error, '密码错误'));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    if (!window.confirm('确定要退出登录吗？')) return;
    try {
      await logoutTelegram();
      toast.success('已退出登录');
      fetchStatus();
    } catch (error) {
      toast.error(getApiErrorMessage(error, '退出失败'));
    }
  };

  const handleResetSession = async () => {
    if (!window.confirm('重置会话将强制删除本地登录文件。如果您遇到了 "Two Different IP Addresses" 错误，请执行此操作。确定继续吗？')) return;
    setLoading(true);
    try {
      await resetTelegramSession();
      toast.success('会话已重置，您可以重新尝试登录了');
      fetchStatus();
      setStep('phone');
    } catch (error) {
      toast.error(getApiErrorMessage(error, '重置失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Telegram"
        title="Telegram 账号管理"
        description="管理 Telegram 登录状态，以便抓取频道消息和补全本地资源库。"
        meta={<StatusBadge status={status.is_authorized ? 'connected' : 'disconnected'}>{status.is_authorized ? '已登录' : '未登录'}</StatusBadge>}
      />

      <div className="row justify-content-center">
        <div className="col-lg-7">
          <TelegramStatusCard status={status} onLogout={handleLogout} onResetSession={handleResetSession} />

          {!status.is_authorized && (
            <Panel className="mb-4">
              <TelegramLoginSteps
                step={step}
                loading={loading}
                phone={phone}
                code={code}
                password={password}
                onPhoneChange={setPhone}
                onCodeChange={setCode}
                onPasswordChange={setPassword}
                onSendCode={handleSendCode}
                onVerifyCode={handleVerifyCode}
                onVerifyPassword={handleVerifyPassword}
                onBackToPhone={() => setStep('phone')}
              />
            </Panel>
          )}

          <TelegramSessionNotice />
        </div>
      </div>
    </div>
  );
}

export default TelegramLoginPage;
