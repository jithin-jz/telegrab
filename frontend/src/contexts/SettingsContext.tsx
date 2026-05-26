import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { load } from '../lib/platform/store';

export type Theme = 'dark' | 'light' | 'system';
export type ViewMode = 'large-grid' | 'medium-grid' | 'list';
export type AccentColor = 'purple' | 'blue' | 'sky' | 'green' | 'orange' | 'pink' | 'rose';
export type ThumbnailQuality = 'low' | 'medium' | 'high';
export type NotificationStyle = 'toast' | 'system' | 'none';
export type StartupFolder = 'last' | 'root' | string; // string = specific folder id

export interface Settings {
  // Appearance
  theme: Theme;
  accentColor: AccentColor;

  // File browser
  viewMode: 'large-grid' | 'medium-grid' | 'list';
  sortField: 'name' | 'size' | 'date';
  sortDirection: 'asc' | 'desc';
  thumbnailQuality: ThumbnailQuality;
  mediaAutoplay: boolean;

  // Transfers
  maxConcurrentUploads: number;
  maxConcurrentDownloads: number;
  defaultDownloadFolder: string | null;
  bandwidthLimitMBps: number; // 0 = unlimited
  autoClearTransfersSec: number; // 0 = never

  // Behavior
  startMinimised: boolean;
  startupFolder: StartupFolder;
  confirmBeforeDelete: boolean;
  notificationStyle: NotificationStyle;

  // Storage
  cacheSizeLimitMB: number; // 0 = unlimited
  autoUpdate: boolean;
  autoSyncInterval: number; // minutes, 0 = manual only
}

export const defaultSettings: Settings = {
  theme: 'dark',
  accentColor: 'purple',
  viewMode: 'medium-grid',
  sortField: 'name',
  sortDirection: 'asc',
  thumbnailQuality: 'medium',
  mediaAutoplay: true,
  maxConcurrentUploads: 6,
  maxConcurrentDownloads: 6,
  defaultDownloadFolder: null,
  bandwidthLimitMBps: 0,
  autoClearTransfersSec: 0,
  startMinimised: false,
  startupFolder: 'last',
  confirmBeforeDelete: true,
  notificationStyle: 'toast',
  cacheSizeLimitMB: 500,
  autoUpdate: true,
  autoSyncInterval: 5,
};

export const ACCENT_COLORS: Record<AccentColor, { label: string; value: string }> = {
  purple: { label: 'Purple', value: '#7c5cff' },
  blue: { label: 'Blue', value: '#3b82f6' },
  sky: { label: 'Sky', value: '#f43f5e' },
  green: { label: 'Green', value: '#22c55e' },
  orange: { label: 'Orange', value: '#f97316' },
  pink: { label: 'Pink', value: '#ec4899' },
  rose: { label: 'Rose', value: '#f43f5e' },
};

interface SettingsContextType {
  settings: Settings;
  updateSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  resetSettings: () => void;
  isLoaded: boolean;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const store = await load('settings.json');
        const saved = await store.get<Settings>('settings');
        if (saved) {
          setSettings({ ...defaultSettings, ...saved });
        }
      } catch {
        // first run — use defaults
      } finally {
        setIsLoaded(true);
      }
    };
    loadSettings();
  }, []);

  // Apply theme + accent color to document
  useEffect(() => {
    if (!isLoaded) return;
    const root = document.documentElement;

    // Theme
    const resolved = settings.theme === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : settings.theme;
    root.setAttribute('data-theme', resolved);

    // Accent color — update --color-primary which all UI components reference
    const accent = ACCENT_COLORS[settings.accentColor]?.value || ACCENT_COLORS.purple.value;
    root.style.setProperty('--color-primary', accent);
    root.style.setProperty('--color-ring', accent);
    root.style.setProperty('--color-telegram-primary', accent);
  }, [isLoaded, settings.theme, settings.accentColor]);

  // Listen for system theme changes
  useEffect(() => {
    if (settings.theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [settings.theme]);

  const persistSettings = useCallback(async (next: Settings) => {
    try {
      const store = await load('settings.json');
      await store.set('settings', next);
      await store.save();
    } catch { /* best-effort */ }
  }, []);

  const updateSetting = useCallback(
    <K extends keyof Settings>(key: K, value: Settings[K]) => {
      setSettings((prev) => {
        const next = { ...prev, [key]: value };
        persistSettings(next);
        return next;
      });
    },
    [persistSettings]
  );

  const resetSettings = useCallback(() => {
    setSettings(defaultSettings);
    persistSettings(defaultSettings);
  }, [persistSettings]);

  return (
    <SettingsContext.Provider value={{ settings, updateSetting, resetSettings, isLoaded }}>
      {children}
    </SettingsContext.Provider>
  );
}

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) throw new Error('useSettings must be used within a SettingsProvider');
  return context;
};
