import React from 'react';

function SubscriptionHelpPanel() {
  return (
    <div className="alert alert-info mt-4">
      <h6 className="alert-heading">使用说明</h6>
      <ul className="mb-0 small">
        <li><strong>精准订阅</strong>：选择 TMDB 作品后，系统会用 Jellyfin 入库状态计算追更进度</li>
        <li><strong>剧集检查</strong>：自动检查只搜索 Jellyfin 最高已入库集之后的下一集</li>
        <li><strong>历史缺失</strong>：中间缺失的集数只展示提醒，需要手动搜索或补入</li>
        <li><strong>质量过滤</strong>：使用正则表达式过滤画质（如 "4K|2160p" 只匹配4K资源）</li>
        <li><strong>定时检查</strong>：系统会按后端调度器配置检查下一集</li>
        <li><strong>手动检查</strong>：点击"检查下一集"立即执行一次订阅检查</li>
      </ul>
    </div>
  );
}

export default SubscriptionHelpPanel;
