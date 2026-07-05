export function summarizeTransferFailure(message) {
  const text = String(message || '').trim();
  if (!text) return '转存失败，未返回具体原因。';

  const statusMatch = text.match(/\b([45]\d{2})\s+Server Error\b/i);
  if (statusMatch) {
    return `外部转存服务返回 ${statusMatch[1]}，资源未提交成功。`;
  }
  if (/CMS 没有更新同步结果/.test(text)) {
    return 'CMS 暂未返回转存结果。';
  }
  if (/分享已取消|分享不存在|资源不存在/.test(text)) {
    return '115 分享已失效或不存在。';
  }
  if (/已经转存过|已转存过|文件已接收/.test(text)) {
    return '目标端已存在该资源。';
  }
  if (/timeout|timed out|超时/i.test(text)) {
    return '外部转存服务请求超时。';
  }
  return text.length > 96 ? `${text.slice(0, 96)}...` : text;
}

export function transferFailureDetail(message) {
  return String(message || '').trim();
}
