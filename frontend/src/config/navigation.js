import {
  Bell,
  Clapperboard,
  Download,
  Gauge,
  Inbox,
  Network,
  ListChecks,
  Satellite,
  Search,
  Settings2,
  Sparkles,
  User,
} from 'lucide-react';

export const navItems = [
  { to: '/', label: '概览', icon: Gauge, end: true, group: '工作区' },
  { to: '/search', label: '搜索', icon: Search, group: '工作区' },
  { to: '/library', label: '资源库', icon: Search, group: '工作区' },
  { to: '/recommendations', label: '推荐', icon: Sparkles, group: '工作区' },
  { to: '/subscriptions', label: '订阅管理', icon: Bell, group: '工作区' },
  { to: '/pending', label: '审核队列', icon: Inbox, group: '转存与运维' },
  { to: '/history', label: '下载历史', icon: Download, group: '转存与运维' },
  { to: '/tasks', label: '任务中心', icon: ListChecks, group: '转存与运维' },
  { to: '/jellyfin', label: 'Jellyfin', icon: Clapperboard, group: '转存与运维' },
  { to: '/system', label: '系统状态', icon: Settings2, group: '系统管理' },
  { to: '/channels', label: '频道配置', icon: Satellite, group: '系统管理' },
  { to: '/proxy', label: '代理设置', icon: Network, group: '系统管理' },
  { to: '/login', label: '账号登录', icon: User, group: '系统管理' },
];

export function visibleNavItemsForUser() {
  return navItems;
}
