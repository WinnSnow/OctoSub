export const APP_NAME = 'OctoSub';
export const APP_LOGIN_TITLE = '网盘资源搜索后台';
export const APP_LOGIN_SUBTITLE = '登录后使用公开实时搜索、本地库搜索和 Telegram 抓取管理。';
export const APP_BRAND_SUBTITLE = '媒体资源工作台';
export const THEME_STORAGE_KEY = 'octosub-theme';
export const APPEARANCE_STORAGE_KEY = 'octosub-appearance';
export const DEFAULT_SUBSCRIPTION_CONFIDENCE = 0.82;
export const HOME_LOCAL_PAGE_SIZE = 30;
export const HOME_LOCAL_SEARCH_DEBOUNCE_MS = 450;
export const HOME_TASK_POLL_INTERVAL_MS = 2000;
export const HOME_TASK_CLEAR_DELAY_MS = 5000;
export const HOME_POSTER_REFRESH_INTERVAL_MS = 2000;
export const HOME_POSTER_REFRESH_DURATION_MS = 60000;

export const PROXY_DEFAULT_CONFIG = {
  protocol: 'socks5',
  host: '127.0.0.1',
  port: 7890,
  username: '',
  password: '',
  enabled: true,
  mode: 'auto',
};

export const PROXY_EXAMPLE_LINK = 'socks5://user:pass@127.0.0.1:1080';
export const JELLYFIN_EXAMPLE_URL = 'http://192.168.1.100:8096';
export const JELLYFIN_ENV_EXAMPLE = `# Jellyfin 配置
JELLYFIN_URL=http://192.168.1.100:8096
JELLYFIN_API_KEY=your_api_key_here`;
