import React, { useEffect, useMemo, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  ChevronDown,
  Film,
  Gauge,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  SunMedium,
  Tv,
  X,
  Zap,
} from 'lucide-react';

import AppearancePanel from './AppearancePanel';
import { APP_BRAND_SUBTITLE, APP_NAME } from '../config/app';
import { visibleNavItemsForUser } from '../config/navigation';
import {
  SEARCH_SCOPE_STORAGE_KEY,
  SEARCH_SCOPES,
  getSearchScopeConfig,
  normalizeSearchScope,
} from '../config/searchScopes';

const SIDEBAR_COLLAPSED_KEY = 'octosub.sidebarCollapsed';

function readStoredSidebarCollapsed() {
  if (typeof window === 'undefined') return false;
  return window.localStorage?.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
}

function itemMatchesPath(item, pathname) {
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}

function childMatchesPath(children, pathname) {
  return children.some(child => itemMatchesPath(child, pathname));
}

function groupedNavItems(navItems) {
  return navItems.reduce((groups, item) => {
    const group = item.group || '工作区';
    const existing = groups.find(entry => entry.label === group);
    if (existing) {
      existing.items.push(item);
    } else {
      groups.push({ label: group, items: [item] });
    }
    return groups;
  }, []);
}

function WorkspaceTopbar() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [scope, setScope] = useState(() => {
    if (typeof window === 'undefined') return 'media';
    return normalizeSearchScope(window.localStorage?.getItem(SEARCH_SCOPE_STORAGE_KEY));
  });
  const scopeConfig = useMemo(() => getSearchScopeConfig(scope), [scope]);

  const updateScope = (value) => {
    const nextScope = normalizeSearchScope(value);
    setScope(nextScope);
    if (typeof window !== 'undefined') {
      window.localStorage?.setItem(SEARCH_SCOPE_STORAGE_KEY, nextScope);
    }
  };

  const submitSearch = (event) => {
    event.preventDefault();
    const query = keyword.trim();
    if (!query) return;
    if (scope === 'library') {
      const params = new URLSearchParams({ q: query });
      navigate(`/library?${params.toString()}`);
    } else {
      const params = new URLSearchParams({ scope, q: query });
      navigate(`/search?${params.toString()}`);
    }
    setKeyword('');
  };

  return (
    <header className="workspace-topbar d-none d-lg-flex">
      <form className="workspace-search" onSubmit={submitSearch} role="search" aria-label="全局搜索">
        <Search size={17} />
        <label className="visually-hidden" htmlFor="workspace-global-search-scope">搜索目标</label>
        <select
          id="workspace-global-search-scope"
          className="workspace-search-scope"
          value={scope}
          onChange={event => updateScope(event.target.value)}
          aria-label="搜索目标"
        >
          {SEARCH_SCOPES.map(item => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
        <label className="workspace-search-copy" htmlFor="workspace-global-search">
          <span>{scopeConfig.label}</span>
          <input
            id="workspace-global-search"
            value={keyword}
            onChange={event => setKeyword(event.target.value)}
            placeholder={scopeConfig.placeholder}
            autoComplete="off"
          />
        </label>
        <button type="submit" className="workspace-search-submit" disabled={!keyword.trim()}>
          搜索
        </button>
      </form>
      <div className="workspace-status-strip">
        <span className="workspace-status-pill connected"><Tv size={14} /> Jellyfin</span>
        <span className="workspace-status-pill running"><Zap size={14} /> 任务状态</span>
        <span className="workspace-status-pill neutral"><Gauge size={14} /> 单人模式</span>
      </div>
    </header>
  );
}

function AppShell({ children, user, theme, onToggleTheme, onLogout, appearanceControls }) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readStoredSidebarCollapsed);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const toggleSidebar = () => setSidebarOpen(open => !open);
  const closeSidebar = () => setSidebarOpen(false);
  const navItems = visibleNavItemsForUser();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage?.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? 'true' : 'false');
    }
  }, [sidebarCollapsed]);

  const handleLogout = async () => {
    await onLogout();
    closeSidebar();
  };

  const toggleGroup = (itemTo) => {
    setExpandedGroups(groups => ({
      ...groups,
      [itemTo]: !groups[itemTo],
    }));
  };
  const navGroups = groupedNavItems(navItems);

  return (
    <div className="app-container">
      <div className="app-background-layer" aria-hidden="true"></div>
      <div className="mobile-header d-lg-none">
        <button className="mobile-menu-btn" onClick={toggleSidebar} aria-label="打开导航">
          <Menu size={22} />
        </button>
        <span className="mobile-title">{APP_NAME}</span>
      </div>

      {sidebarOpen && (
        <div className="sidebar-overlay d-lg-none" onClick={closeSidebar}></div>
      )}

      <div className={`sidebar-container ${sidebarOpen ? 'open' : ''} ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">
            <Film size={22} />
          </div>
          <div className="brand-copy">
            <div className="brand-title">{APP_NAME}</div>
            <div className="brand-subtitle">{APP_BRAND_SUBTITLE}</div>
          </div>
          <button
            className="sidebar-collapse-toggle d-none d-lg-grid"
            onClick={() => setSidebarCollapsed(collapsed => !collapsed)}
            aria-label={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
          <button className="sidebar-close d-lg-none" onClick={closeSidebar} aria-label="关闭导航">
            <X size={20} />
          </button>
        </div>

        <ul className="nav nav-pills flex-column mb-auto px-2">
          {navGroups.map(group => (
            <li className="nav-section" key={group.label}>
              {!sidebarCollapsed && <div className="nav-section-label">{group.label}</div>}
              <ul className="nav-section-list">
                {group.items.map(({ to, label, icon: Icon, end, children: childItems = [] }) => {
                  const hasChildren = childItems.length > 0;
                  const parentActive = itemMatchesPath({ to, end }, location.pathname);
                  const childActive = childMatchesPath(childItems, location.pathname);
                  const isExpanded = !sidebarCollapsed && hasChildren && (expandedGroups[to] || childActive);

                  return (
                    <li className="nav-item" key={to}>
                      <div className={`nav-parent-row ${hasChildren ? 'has-children' : ''} ${parentActive || childActive ? 'active-row' : ''}`.trim()}>
                        <NavLink
                          to={to}
                          className={({ isActive }) => `nav-link ${isActive || childActive ? 'active-link' : ''}`}
                          onClick={closeSidebar}
                          end={end}
                          title={sidebarCollapsed ? label : undefined}
                          aria-label={sidebarCollapsed ? label : undefined}
                        >
                          <Icon size={18} />
                          <span className="nav-label">{label}</span>
                        </NavLink>
                        {hasChildren && !sidebarCollapsed && (
                          <button
                            type="button"
                            className="nav-group-toggle"
                            onClick={() => toggleGroup(to)}
                            aria-label={`${isExpanded ? '收起' : '展开'}${label}子菜单`}
                            aria-expanded={isExpanded}
                          >
                            <ChevronDown className={isExpanded ? 'expanded' : ''} size={15} />
                          </button>
                        )}
                      </div>
                      {isExpanded && (
                        <div className="nav-submenu">
                          {childItems.map(({ to: childTo, label: childLabel, icon: ChildIcon, end: childEnd }) => (
                            <NavLink
                              key={childTo}
                              to={childTo}
                              className={({ isActive }) => `nav-link nav-sublink ${isActive ? 'active-link' : ''}`}
                              onClick={closeSidebar}
                              end={childEnd}
                            >
                              <ChildIcon size={16} />
                              <span className="nav-label">{childLabel}</span>
                            </NavLink>
                          ))}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>

        <div className="sidebar-account">
          <div className="account-avatar">
            <Settings size={16} />
          </div>
          <div className="account-copy">
            <div>已登录</div>
            <span>{user.username}</span>
          </div>
          <button
            className="account-theme"
            onClick={onToggleTheme}
            aria-label={theme === 'dark' ? '切换到白天模式' : '切换到夜间模式'}
            title={theme === 'dark' ? '白天模式' : '夜间模式'}
          >
            {theme === 'dark' ? <SunMedium size={16} /> : <Moon size={16} />}
          </button>
          <button className="account-logout" onClick={handleLogout} aria-label="退出登录">
            <LogOut size={16} />
          </button>
          <button
            className="account-appearance"
            onClick={() => setAppearanceOpen(true)}
            aria-label="外观设置"
            title="外观设置"
          >
            <Settings size={16} />
          </button>
        </div>
      </div>

      <div className="main-content-wrapper">
        <WorkspaceTopbar />
        <div className="main-content p-3 p-lg-4">
          <div className="container-fluid">
            {children}
          </div>
        </div>
      </div>
      {appearanceControls && (
        <AppearancePanel
          open={appearanceOpen}
          onClose={() => setAppearanceOpen(false)}
          theme={theme}
          appearance={appearanceControls.appearance}
          skinPresets={appearanceControls.skinPresets}
          accentSwatches={appearanceControls.accentSwatches}
          onToggleTheme={onToggleTheme}
          onApplySkinPreset={appearanceControls.applySkinPreset}
          onSetAppearance={appearanceControls.setAppearance}
          onSaveBackgroundImage={appearanceControls.saveBackgroundImage}
          onRemoveBackgroundImage={appearanceControls.removeBackgroundImage}
          onResetAppearance={appearanceControls.resetAppearance}
        />
      )}
    </div>
  );
}

export default AppShell;
