export function normalizeWhitespace(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

export function truncateText(value, length = 80) {
  const text = String(value || '');
  if (text.length <= length) return text;
  return `${text.slice(0, length)}...`;
}

export function formatDateTime(value, locale = 'zh-CN') {
  if (!value) return '未知时间';
  return new Date(value).toLocaleString(locale, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
