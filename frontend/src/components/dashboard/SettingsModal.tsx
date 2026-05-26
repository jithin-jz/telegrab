import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, RotateCcw, Download, Trash2, RefreshCw,
  Palette, HardDrive, Info, CheckCircle2, Sun, Moon, Laptop,
  FolderOpen, Zap, LogOut,
} from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { open as openDialog } from '../../lib/platform/dialog';
import { open as shellOpen } from '../../lib/platform/shell';
import { useUpdateCheck } from '../../hooks/useUpdateCheck';
import { toast } from 'sonner';
import {
  useSettings, ACCENT_COLORS,
  type Theme, type AccentColor, type ThumbnailQuality,
} from '../../contexts/SettingsContext';
import { useConfirm } from '../../contexts/ConfirmContext';
import { APP_VERSION } from '../../lib/version';

import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { Slider } from '../ui/slider';
import { Separator } from '../ui/separator';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSync: () => void;
  onLogout: () => void;
  isSyncing: boolean;
}

type Tab = 'appearance' | 'transfers' | 'behavior' | 'storage' | 'about';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'appearance', label: 'Appearance', icon: <Palette className="h-4 w-4" /> },
  { id: 'transfers', label: 'Transfers', icon: <Download className="h-4 w-4" /> },
  { id: 'behavior', label: 'Behavior', icon: <Zap className="h-4 w-4" /> },
  { id: 'storage', label: 'Storage', icon: <HardDrive className="h-4 w-4" /> },
  { id: 'about', label: 'About', icon: <Info className="h-4 w-4" /> },
];

export function SettingsModal({ isOpen, onClose, onSync, onLogout, isSyncing }: SettingsModalProps) {
  const { updateSetting, resetSettings } = useSettings();
  const { confirm } = useConfirm();
  const {
    available, version, checking, downloading, progress,
    checkForUpdates, downloadAndInstall,
  } = useUpdateCheck();

  const [activeTab, setActiveTab] = useState<Tab>('appearance');
  const [clearing, setClearing] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const [cacheSize, setCacheSize] = useState<string>('...');

  useEffect(() => {
    if (isOpen && !hasChecked && !checking) {
      setHasChecked(true);
      checkForUpdates();
    }
  }, [isOpen, hasChecked, checking, checkForUpdates]);

  useEffect(() => {
    if (isOpen) {
      invoke<number>('cmd_get_cache_size').then((bytes) => {
        setCacheSize(`${(bytes / (1024 * 1024)).toFixed(1)} MB`);
      }).catch(() => setCacheSize('Unknown'));
    }
  }, [isOpen]);

  const handleClearCache = async () => {
    setClearing(true);
    try {
      await invoke('cmd_clear_cache');
      setCacheSize('0 MB');
      toast.success('Cache cleared');
    } catch { toast.error('Failed to clear cache'); }
    finally { setClearing(false); }
  };

  const handlePickDownloadFolder = async () => {
    try {
      const folder = await openDialog({ directory: true, multiple: false });
      if (folder) updateSetting('defaultDownloadFolder', folder as string);
    } catch { /* cancelled */ }
  };

  const handleReset = async () => {
    const ok = await confirm({ title: 'Reset Settings', message: 'Reset all settings to their default values? This cannot be undone.' });
    if (ok) { resetSettings(); toast.success('Settings reset to defaults'); }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.97, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 6 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="bg-surface/80 backdrop-blur-xl border-hairline relative flex w-full max-w-[680px] overflow-hidden rounded-2xl border shadow-2xl"
          style={{ height: '520px' }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Sidebar nav */}
          <nav className="border-hairline flex w-[180px] flex-shrink-0 flex-col border-r bg-canvas py-3">
            <div className="px-4 pb-3">
              <h2 className="text-foreground text-sm font-semibold">Settings</h2>
            </div>
            <div className="flex-1 space-y-0.5 px-2">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-all ${
                    activeTab === tab.id
                      ? 'bg-primary/10 text-primary'
                      : 'text-slate hover:text-foreground hover:bg-surface-soft'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="border-hairline border-t px-3 pt-3 space-y-1">
              <button
                onClick={onLogout}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium text-slate transition-colors hover:bg-surface-soft hover:text-foreground"
              >
                <LogOut className="h-3.5 w-3.5" />Sign Out
              </button>
              <button
                onClick={handleReset}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium text-rose-400/80 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
              >
                <RotateCcw className="h-3.5 w-3.5" />Reset All
              </button>
            </div>
          </nav>

          {/* Content area */}
          <div className="flex flex-1 flex-col">
            {/* Header */}
            <div className="border-hairline flex items-center justify-between border-b px-6 py-3.5">
              <h3 className="text-foreground text-[15px] font-semibold">
                {TABS.find((t) => t.id === activeTab)?.label}
              </h3>
              <button onClick={onClose} className="text-slate hover:text-foreground rounded-md p-1 transition-colors hover:bg-surface-soft">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Scrollable content */}
            <div className="custom-scrollbar flex-1 overflow-y-auto px-6 py-5">
              {activeTab === 'appearance' && <AppearanceTab />}
              {activeTab === 'transfers' && <TransfersTab onPickFolder={handlePickDownloadFolder} />}
              {activeTab === 'behavior' && <BehaviorTab onSync={onSync} isSyncing={isSyncing} />}
              {activeTab === 'storage' && <StorageTab cacheSize={cacheSize} clearing={clearing} onClearCache={handleClearCache} />}
              {activeTab === 'about' && <AboutTab available={available} version={version} checking={checking} downloading={downloading} progress={progress} checkForUpdates={checkForUpdates} downloadAndInstall={downloadAndInstall} />}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ────────────────────────── Tab Components ──────────────────────────

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-foreground text-[13px] font-medium">{label}</p>
        {description && <p className="text-slate mt-0.5 text-[11px] leading-tight">{description}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

function SegmentedControl<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string; icon?: React.ReactNode }[]; onChange: (v: T) => void }) {
  return (
    <div className="border-hairline inline-flex rounded-lg border bg-surface-soft p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-all ${
            value === opt.value
              ? 'bg-surface text-foreground shadow-sm border-hairline border'
              : 'text-slate hover:text-foreground'
          }`}
        >
          {opt.icon}{opt.label}
        </button>
      ))}
    </div>
  );
}

function AppearanceTab() {
  const { settings, updateSetting } = useSettings();
  return (
    <div className="space-y-1">
      <SettingRow label="Theme" description="Choose your preferred color scheme">
        <SegmentedControl
          value={settings.theme}
          options={[
            { value: 'dark' as Theme, label: 'Dark', icon: <Moon className="h-3 w-3" /> },
            { value: 'light' as Theme, label: 'Light', icon: <Sun className="h-3 w-3" /> },
            { value: 'system' as Theme, label: 'System', icon: <Laptop className="h-3 w-3" /> },
          ]}
          onChange={(v) => updateSetting('theme', v)}
        />
      </SettingRow>

      <Separator />

      <div className="py-3">
        <p className="text-foreground text-[13px] font-medium">Accent Color</p>
        <p className="text-slate mt-0.5 text-[11px]">Customize the primary UI color</p>
        <div className="mt-3 flex gap-2.5">
          {(Object.entries(ACCENT_COLORS) as [AccentColor, { label: string; value: string }][]).map(([key, { label, value }]) => (
            <button
              key={key}
              onClick={() => updateSetting('accentColor', key)}
              className={`group relative flex h-7 w-7 items-center justify-center rounded-full transition-transform ${
                settings.accentColor === key ? 'scale-110' : 'hover:scale-105'
              }`}
              title={label}
            >
              <span
                className={`h-6 w-6 rounded-full ring-2 ring-offset-2 ring-offset-[var(--color-surface)] ${
                  settings.accentColor === key ? 'ring-foreground' : 'ring-transparent'
                }`}
                style={{ backgroundColor: value }}
              />
            </button>
          ))}
        </div>
      </div>

      <Separator />

      <SettingRow label="Default view" description="Choose how files are displayed">
        <SegmentedControl
          value={settings.viewMode}
          options={[
            { value: 'large-grid' as const, label: 'Large' },
            { value: 'medium-grid' as const, label: 'Medium' },
            { value: 'list' as const, label: 'List' },
          ]}
          onChange={(v) => updateSetting('viewMode', v)}
        />
      </SettingRow>

      <Separator />

      <SettingRow label="Thumbnail quality" description="Higher quality uses more bandwidth">
        <SegmentedControl
          value={settings.thumbnailQuality}
          options={[
            { value: 'low' as ThumbnailQuality, label: 'Low' },
            { value: 'medium' as ThumbnailQuality, label: 'Med' },
            { value: 'high' as ThumbnailQuality, label: 'High' },
          ]}
          onChange={(v) => updateSetting('thumbnailQuality', v)}
        />
      </SettingRow>
    </div>
  );
}

function TransfersTab({ onPickFolder }: { onPickFolder: () => void }) {
  const { settings, updateSetting } = useSettings();
  return (
    <div className="space-y-1">
      {/* Download folder */}
      <div className="py-3">
        <p className="text-foreground text-[13px] font-medium">Default download location</p>
        <p className="text-slate mt-0.5 text-[11px]">Skip the save dialog for downloads</p>
        <div className="mt-2.5 flex items-center gap-2">
          <div className="border-hairline flex-1 truncate rounded-lg border bg-surface-soft px-3 py-2 text-[12px] text-slate">
            {settings.defaultDownloadFolder || 'Ask every time'}
          </div>
          <Button size="sm" variant="outline" onClick={onPickFolder} className="h-8 text-xs">
            <FolderOpen className="mr-1.5 h-3.5 w-3.5" />Browse
          </Button>
          {settings.defaultDownloadFolder && (
            <Button size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => updateSetting('defaultDownloadFolder', null)}>
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <Separator />

      {/* Concurrent uploads */}
      <div className="py-3">
        <div className="flex items-center justify-between">
          <p className="text-foreground text-[13px] font-medium">Concurrent uploads</p>
          <span className="bg-primary/10 text-primary rounded-md px-2 py-0.5 text-[11px] font-bold">{settings.maxConcurrentUploads}</span>
        </div>
        <Slider className="mt-3" value={[settings.maxConcurrentUploads]} onValueChange={([v]) => updateSetting('maxConcurrentUploads', v)} min={1} max={10} step={1} />
      </div>

      {/* Concurrent downloads */}
      <div className="py-3">
        <div className="flex items-center justify-between">
          <p className="text-foreground text-[13px] font-medium">Concurrent downloads</p>
          <span className="bg-primary/10 text-primary rounded-md px-2 py-0.5 text-[11px] font-bold">{settings.maxConcurrentDownloads}</span>
        </div>
        <Slider className="mt-3" value={[settings.maxConcurrentDownloads]} onValueChange={([v]) => updateSetting('maxConcurrentDownloads', v)} min={1} max={10} step={1} />
      </div>

    </div>
  );
}

function BehaviorTab({ onSync, isSyncing }: { onSync: () => void; isSyncing: boolean }) {
  const { settings, updateSetting } = useSettings();
  return (
    <div className="space-y-1">
      {/* Sync section */}
      <div className="py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-foreground text-[13px] font-medium">Sync folders</p>
            <p className="text-slate mt-0.5 text-[11px]">Refresh folder list from Telegram</p>
          </div>
          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={onSync} disabled={isSyncing}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </Button>
        </div>
      </div>

      {/* Auto-sync interval */}
      <div className="py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-foreground text-[13px] font-medium">Auto-sync</p>
            <p className="text-slate mt-0.5 text-[11px]">Automatically refresh folders periodically</p>
          </div>
          <span className="text-slate text-[11px]">
            {settings.autoSyncInterval === 0 ? 'Off' : `Every ${settings.autoSyncInterval} min`}
          </span>
        </div>
        <Slider className="mt-3" value={[settings.autoSyncInterval]} onValueChange={([v]) => updateSetting('autoSyncInterval', v)} min={0} max={30} step={1} />
      </div>

      <Separator />

      <SettingRow label="Confirm before delete" description="Show a dialog before permanently deleting files">
        <Switch checked={settings.confirmBeforeDelete} onCheckedChange={(v) => updateSetting('confirmBeforeDelete', v)} />
      </SettingRow>
      <Separator />
      <SettingRow label="Media autoplay" description="Auto-play videos and audio when opened">
        <Switch checked={settings.mediaAutoplay} onCheckedChange={(v) => updateSetting('mediaAutoplay', v)} />
      </SettingRow>
      <Separator />
      <SettingRow label="Start minimised" description="Launch the app hidden in the system tray">
        <Switch checked={settings.startMinimised} onCheckedChange={(v) => updateSetting('startMinimised', v)} />
      </SettingRow>
      <Separator />
      <SettingRow label="Startup folder" description="Which folder to show when the app launches">
        <SegmentedControl
          value={settings.startupFolder as 'last' | 'root'}
          options={[
            { value: 'last' as const, label: 'Last used' },
            { value: 'root' as const, label: 'Root' },
          ]}
          onChange={(v) => updateSetting('startupFolder', v)}
        />
      </SettingRow>
    </div>
  );
}

function StorageTab({ cacheSize, clearing, onClearCache }: { cacheSize: string; clearing: boolean; onClearCache: () => void }) {
  const { settings, updateSetting } = useSettings();
  return (
    <div className="space-y-1">
      {/* Cache info */}
      <div className="py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-foreground text-[13px] font-medium">Preview cache</p>
            <p className="text-slate mt-0.5 text-[11px]">Thumbnails, previews, and temporary files</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-foreground text-sm font-semibold">{cacheSize}</span>
            <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={onClearCache} disabled={clearing}>
              <Trash2 className="mr-1 h-3 w-3" />{clearing ? 'Clearing...' : 'Clear'}
            </Button>
          </div>
        </div>
      </div>

      <Separator />

      <div className="py-3">
        <div className="flex items-center justify-between">
          <p className="text-foreground text-[13px] font-medium">Cache limit</p>
          <span className="text-slate text-[11px]">
            {settings.cacheSizeLimitMB === 0 ? 'Unlimited' : `${settings.cacheSizeLimitMB} MB`}
          </span>
        </div>
        <Slider className="mt-3" value={[settings.cacheSizeLimitMB]} onValueChange={([v]) => updateSetting('cacheSizeLimitMB', v)} min={0} max={2000} step={100} />
      </div>

      <Separator />

      <SettingRow label="Auto-update" description="Check for updates and install automatically">
        <Switch checked={settings.autoUpdate} onCheckedChange={(v) => updateSetting('autoUpdate', v)} />
      </SettingRow>
    </div>
  );
}

function AboutTab({ available, version, checking, downloading, progress, checkForUpdates, downloadAndInstall }: {
  available: boolean; version: string | null; checking: boolean; downloading: boolean; progress: number;
  checkForUpdates: () => void; downloadAndInstall: () => void;
}) {
  return (
    <div className="space-y-5">
      {/* App info */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#f43f5e]">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" className="h-7 w-7">
            <text x="256" y="370" fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="240" fill="#ffffff" textAnchor="middle">tb</text>
          </svg>
        </div>
        <div>
          <p className="text-foreground text-base font-semibold">Telegrab</p>
          <p className="text-slate text-[12px]">v{APP_VERSION} · Your private cloud</p>
        </div>
      </div>

      <Separator />

      {/* Update */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <CheckCircle2 className={`h-4 w-4 ${available ? 'text-amber-400' : 'text-emerald-500'}`} />
          <span className="text-foreground text-[13px]">
            {available ? `Update ${version} available` : 'Up to date'}
          </span>
        </div>
        {available ? (
          <Button size="sm" onClick={downloadAndInstall} disabled={downloading}>
            {downloading ? `${progress}%` : 'Install'}
          </Button>
        ) : (
          <Button size="sm" variant="ghost" onClick={checkForUpdates} disabled={checking}>
            <RefreshCw className={`h-3.5 w-3.5 ${checking ? 'animate-spin' : ''}`} />
          </Button>
        )}
      </div>

      <Separator />

      {/* About paragraph */}
      <p className="text-slate text-[12px] leading-relaxed">
        Telegrab turns Telegram into your personal unlimited cloud storage. Upload, stream, and manage files across all your devices no storage caps, no subscriptions. Your files stay private between you and Telegram.
      </p>

      <Separator />

      {/* Links + profile in one row at bottom */}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" className="text-xs" onClick={() => shellOpen('https://github.com/jithin-jz/telegrab')}>GitHub</Button>
        <Button variant="outline" size="sm" className="text-xs" onClick={() => shellOpen('https://github.com/jithin-jz/telegrab/issues')}>Report Bug</Button>
        <button className="ml-auto text-slate hover:text-foreground transition-opacity" onClick={() => shellOpen('https://github.com/jithin-jz')} title="@jithin-jz">
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21.5c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z"/></svg>
        </button>
      </div>
    </div>
  );
}
