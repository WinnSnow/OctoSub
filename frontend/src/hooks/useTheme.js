import { useEffect, useState } from 'react';

import { APPEARANCE_STORAGE_KEY, THEME_STORAGE_KEY } from '../config/app';

const BACKGROUND_DB_NAME = 'octosub-appearance';
const BACKGROUND_STORE_NAME = 'assets';
const BACKGROUND_IMAGE_KEY = 'backgroundImage';

export const SKIN_PRESETS = [
  {
    id: 'noir',
    label: 'Noir Ops',
    description: '默认深色工作台，适合长期管理资源。',
    theme: 'dark',
    accent: '#f97316',
  },
  {
    id: 'clean',
    label: 'Clean Console',
    description: '清爽浅色控制台，适合白天和信息密集页面。',
    theme: 'light',
    accent: '#2563eb',
  },
  {
    id: 'cinema',
    label: 'Cinema Glass',
    description: '海报背景与半透明界面，适合影视推荐浏览。',
    theme: 'dark',
    accent: '#e11d48',
  },
  {
    id: 'paper',
    label: 'Paper Light',
    description: '低干扰阅读风格，列表和详情页更平静。',
    theme: 'light',
    accent: '#0f766e',
  },
  {
    id: 'oled',
    label: 'OLED Night',
    description: '接近纯黑的夜间模式，适合手机屏幕。',
    theme: 'dark',
    accent: '#22d3ee',
  },
];

export const ACCENT_SWATCHES = ['#4f8cff', '#f97316', '#e11d48', '#8b5cf6', '#0f766e', '#22c55e'];

const DEFAULT_APPEARANCE = {
  skinPreset: 'noir',
  accentColor: '#f97316',
  backgroundOverlay: 72,
  backgroundBlur: 0,
  surfaceOpacity: 96,
  density: 'comfortable',
  contrastMode: 'standard',
  hasBackgroundImage: false,
  backgroundImageName: '',
};

const CINEMA_BACKGROUND_APPEARANCE = {
  skinPreset: 'cinema',
  accentColor: '#e11d48',
  backgroundOverlay: 34,
  backgroundBlur: 1,
  surfaceOpacity: 76,
};

function clampNumber(value, min, max, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

function normalizeAppearance(input = {}) {
  const preset = SKIN_PRESETS.some(item => item.id === input.skinPreset)
    ? input.skinPreset
    : DEFAULT_APPEARANCE.skinPreset;
  return {
    ...DEFAULT_APPEARANCE,
    ...input,
    skinPreset: preset,
    accentColor: /^#[0-9a-fA-F]{6}$/.test(input.accentColor || '')
      ? input.accentColor
      : DEFAULT_APPEARANCE.accentColor,
    backgroundOverlay: clampNumber(
      input.backgroundOverlay,
      0,
      92,
      DEFAULT_APPEARANCE.backgroundOverlay,
    ),
    backgroundBlur: clampNumber(input.backgroundBlur, 0, 20, DEFAULT_APPEARANCE.backgroundBlur),
    surfaceOpacity: clampNumber(input.surfaceOpacity, 72, 100, DEFAULT_APPEARANCE.surfaceOpacity),
    density: input.density === 'compact' ? 'compact' : 'comfortable',
    contrastMode: input.contrastMode === 'high' ? 'high' : 'standard',
    hasBackgroundImage: Boolean(input.hasBackgroundImage),
    backgroundImageName: typeof input.backgroundImageName === 'string' ? input.backgroundImageName : '',
  };
}

function getStoredAppearance() {
  if (typeof window === 'undefined') return DEFAULT_APPEARANCE;
  try {
    const saved = window.localStorage.getItem(APPEARANCE_STORAGE_KEY);
    return normalizeAppearance(saved ? JSON.parse(saved) : DEFAULT_APPEARANCE);
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

function openAppearanceDb() {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(BACKGROUND_DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(BACKGROUND_STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getStoredBackgroundImage() {
  if (typeof window === 'undefined' || !window.indexedDB) return '';
  const db = await openAppearanceDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(BACKGROUND_STORE_NAME, 'readonly');
    const request = tx.objectStore(BACKGROUND_STORE_NAME).get(BACKGROUND_IMAGE_KEY);
    request.onsuccess = () => resolve(request.result || '');
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

async function saveStoredBackgroundImage(dataUrl) {
  if (typeof window === 'undefined' || !window.indexedDB) return;
  const db = await openAppearanceDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(BACKGROUND_STORE_NAME, 'readwrite');
    tx.objectStore(BACKGROUND_STORE_NAME).put(dataUrl, BACKGROUND_IMAGE_KEY);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}

async function clearStoredBackgroundImage() {
  if (typeof window === 'undefined' || !window.indexedDB) return;
  const db = await openAppearanceDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(BACKGROUND_STORE_NAME, 'readwrite');
    tx.objectStore(BACKGROUND_STORE_NAME).delete(BACKGROUND_IMAGE_KEY);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}

function getPreferredTheme() {
  if (typeof window === 'undefined') return 'dark';
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  const appearance = getStoredAppearance();
  const preset = SKIN_PRESETS.find(item => item.id === appearance.skinPreset);
  if (preset?.theme) return preset.theme;
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function useTheme() {
  const [theme, setTheme] = useState(getPreferredTheme);
  const [appearance, setAppearanceState] = useState(getStoredAppearance);
  const [backgroundImage, setBackgroundImage] = useState('');

  useEffect(() => {
    let mounted = true;
    if (!appearance.hasBackgroundImage) {
      setBackgroundImage('');
      return () => {
        mounted = false;
      };
    }
    getStoredBackgroundImage()
      .then(dataUrl => {
        if (mounted) setBackgroundImage(dataUrl);
      })
      .catch(() => {
        if (mounted) setBackgroundImage('');
      });
    return () => {
      mounted = false;
    };
  }, [appearance.hasBackgroundImage]);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    root.setAttribute('data-bs-theme', theme);
    root.setAttribute('data-skin', appearance.skinPreset);
    root.setAttribute('data-density', appearance.density);
    root.setAttribute('data-contrast', appearance.contrastMode);
    root.style.setProperty('--user-accent-color', appearance.accentColor);
    root.style.setProperty('--primary-color', appearance.accentColor);
    root.style.setProperty('--background-overlay-strength', `${appearance.backgroundOverlay}%`);
    root.style.setProperty('--background-blur', `${appearance.backgroundBlur}px`);
    root.style.setProperty('--surface-opacity', `${appearance.surfaceOpacity}%`);
    root.style.setProperty('--app-background-image', backgroundImage ? `url("${backgroundImage}")` : 'none');
    document.body.setAttribute('data-theme', theme);
    document.body.setAttribute('data-skin', appearance.skinPreset);
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    window.localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(appearance));
  }, [appearance, backgroundImage, theme]);

  const toggleTheme = () => {
    setTheme(current => (current === 'dark' ? 'light' : 'dark'));
  };

  const setAppearance = (nextAppearance) => {
    setAppearanceState(current => normalizeAppearance({
      ...current,
      ...(typeof nextAppearance === 'function' ? nextAppearance(current) : nextAppearance),
    }));
  };

  const applySkinPreset = (skinPreset) => {
    const preset = SKIN_PRESETS.find(item => item.id === skinPreset);
    if (!preset) return;
    setTheme(preset.theme);
    setAppearance({
      skinPreset: preset.id,
      accentColor: preset.accent,
    });
  };

  const saveBackgroundImage = async (file, dataUrl) => {
    await saveStoredBackgroundImage(dataUrl);
    setBackgroundImage(dataUrl);
    setTheme('dark');
    setAppearance({
      ...CINEMA_BACKGROUND_APPEARANCE,
      hasBackgroundImage: true,
      backgroundImageName: file?.name || '自定义背景',
    });
  };

  const removeBackgroundImage = async () => {
    await clearStoredBackgroundImage();
    setBackgroundImage('');
    setAppearance({
      hasBackgroundImage: false,
      backgroundImageName: '',
    });
  };

  const resetAppearance = async () => {
    await clearStoredBackgroundImage();
    setTheme('dark');
    setBackgroundImage('');
    setAppearanceState(DEFAULT_APPEARANCE);
  };

  return {
    theme,
    appearance,
    backgroundImage,
    toggleTheme,
    setAppearance,
    applySkinPreset,
    saveBackgroundImage,
    removeBackgroundImage,
    resetAppearance,
    skinPresets: SKIN_PRESETS,
    accentSwatches: ACCENT_SWATCHES,
  };
}
