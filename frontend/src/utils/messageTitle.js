import { normalizeWhitespace } from './text';

export function hasMeaningfulTitle(value) {
  const text = normalizeWhitespace(value);
  return text !== '无标题' && text !== '无标题资源' && /[\u4e00-\u9fffA-Za-z0-9]/.test(text);
}

export function cleanTitle(value) {
  return normalizeWhitespace(value)
    .replace(/(?:链接|资源|分享)\s*[:：]?\s*$/, '')
    .replace(/[\(（\[{【]\s*$/, '')
    .trim();
}

export function extractTextTitle(text) {
  const ignored = ['评分', '类型', '地区', '语言', '主演', '简介', '链接', '投稿人', '大小', '标签', '资源', '点击跳转', '发行时间', '上映时间', '首播', '首播时间', '更新', '更新状态', '剧情简介'];
  const labeledTitlePattern = /^(?:名称|片名|剧名|标题|资源名称)\s*[:：]\s*(.+)$/;
  const isNonTitleFragment = (value) => {
    const line = normalizeWhitespace(value);
    return (
      /^(?:发行时间|上映时间|首播|首播时间|更新|更新状态|评分|类型|地区|语言|主演|简介|剧情简介|大小|标签)\s*[:：]/.test(line) ||
      /^[-–—_/\\.:：\s]*$/.test(line) ||
      /^(?:19|20)\d{2}(?:[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?)?$/.test(line) ||
      /^[-–—_/\\]\s*\d{1,2}(?:[-/月]\d{1,2}日?)?$/.test(line)
    );
  };

  for (const rawLine of String(text || '').split('\n')) {
    const line = cleanTitle(rawLine);
    const labeledTitle = line.match(labeledTitlePattern)?.[1];
    if (hasMeaningfulTitle(labeledTitle)) return cleanTitle(labeledTitle);
    if (!hasMeaningfulTitle(line)) continue;
    if (isNonTitleFragment(line)) continue;
    if (ignored.some(label => line.startsWith(label) || line.startsWith(`${label}：`) || line.startsWith(`${label}:`))) continue;
    return line;
  }

  const compact = cleanTitle(text);
  const labeledTitle = compact.match(labeledTitlePattern)?.[1];
  if (hasMeaningfulTitle(labeledTitle)) return cleanTitle(labeledTitle);
  return isNonTitleFragment(compact) ? '' : compact;
}

export function resolveMessageTitle(message) {
  const candidates = [
    extractTextTitle(message.title),
    extractTextTitle(message.payload?.title),
    extractTextTitle(message.payload?.description),
    extractTextTitle(message.payload?.raw_text),
    message.subscription_keyword,
    '无标题资源',
  ];
  return candidates.find(hasMeaningfulTitle) || '无标题资源';
}
