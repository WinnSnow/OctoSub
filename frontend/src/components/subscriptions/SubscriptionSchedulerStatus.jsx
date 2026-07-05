import React from 'react';

import { formatDateTime } from '../../utils/text';

function SubscriptionSchedulerStatus({ scheduler }) {
  if (!scheduler) return null;
  const dailyJob = scheduler.jobs?.find(job => job.id === 'daily_subscription_check');

  return (
    <div className="alert alert-info py-2 d-flex flex-wrap gap-3 align-items-center">
      <span>定时检查：{scheduler.check_interval_label || `每天 ${scheduler.check_time}`} {scheduler.timezone || ''}</span>
      <span>状态：{scheduler.enabled ? '运行中' : '未运行'}</span>
      {dailyJob?.next_run_time && (
        <span>下次：{formatDateTime(dailyJob.next_run_time)}</span>
      )}
      {scheduler.latest_subscription_checked_at && (
        <span>最近库检查：{formatDateTime(scheduler.latest_subscription_checked_at)}</span>
      )}
      {scheduler.catchup_reason && (
        <span>{scheduler.catchup_needed ? '需补跑' : '补跑状态'}：{scheduler.catchup_reason}</span>
      )}
      {scheduler.last_check?.status && (
        <span>上次：{scheduler.last_check.status} {scheduler.last_check.finished_at || scheduler.last_check.started_at || ''}</span>
      )}
    </div>
  );
}

export default SubscriptionSchedulerStatus;
