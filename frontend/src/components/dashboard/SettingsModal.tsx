import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  RotateCcw,
  Download,
  Trash2,
  Globe,
  Copy,
  Check,
  RefreshCw,
  ArrowUpCircle,
  Settings2,
  Cpu,
  Info,
  CheckCircle2,
} from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { open as shellOpen } from '../../lib/platform/shell';
import { useUpdateCheck } from '../../hooks/useUpdateCheck';
import { toast } from 'sonner';
import { useSettings } from '../../contexts/SettingsContext';
import { useConfirm } from '../../contexts/ConfirmContext';
import { cn } from '../../lib/cn';
import { APP_VERSION } from '../../lib/version';

// UI Components
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Input } from '../ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';
import { Switch } from '../ui/switch';
import { Slider } from '../ui/slider';
import { Label } from '../ui/label';
import { Separator } from '../ui/separator';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ApiSettings {
  enabled: boolean;
  port: number;
  key_set: boolean;
  running: boolean;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { settings, updateSetting, resetSettings } = useSettings();
  const { confirm } = useConfirm();
  const {
    available,
    version,
    checking,
    downloading,
    progress,
    checkForUpdates,
    downloadAndInstall,
  } = useUpdateCheck();
  
  const [clearing, setClearing] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const [apiSettings, setApiSettings] = useState<ApiSettings>({
    enabled: false,
    port: 8550,
    key_set: false,
    running: false,
  });
  const [apiPort, setApiPort] = useState('8550');
  const [apiLoading, setApiLoading] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [keyCopied, setKeyCopied] = useState(false);

  const fetchApiSettings = useCallback(async () => {
    try {
      const result = await invoke<ApiSettings>('cmd_get_api_settings');
      setApiSettings(result);
      setApiPort(result.port.toString());
    } catch {
      // API settings not available
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchApiSettings();
      setGeneratedKey(null);
      setKeyCopied(false);
    }
  }, [isOpen, fetchApiSettings]);

  // Auto-check for updates the first time the modal opens. Subsequent
  // opens reuse the cached state until the user hits "Check again".
  useEffect(() => {
    if (isOpen && !hasChecked && !checking) {
      setHasChecked(true);
      checkForUpdates();
    }
  }, [isOpen, hasChecked, checking, checkForUpdates]);

  useEffect(() => {
    if (!isOpen || !apiSettings.enabled) return;
    const interval = setInterval(fetchApiSettings, 3000);
    return () => clearInterval(interval);
  }, [isOpen, apiSettings.enabled, fetchApiSettings]);

  const handleApiToggle = async (enabled: boolean) => {
    setApiLoading(true);
    try {
      const port = parseInt(apiPort, 10);
      if (isNaN(port) || port < 1024 || port > 65535) {
        toast.error('Port must be between 1024 and 65535');
        setApiLoading(false);
        return;
      }
      const result = await invoke<ApiSettings>('cmd_update_api_settings', {
        enabled,
        port,
      });
      setApiSettings(result);
      toast.success(result.enabled ? 'API server started' : 'API server stopped');
    } catch (e) {
      toast.error(`Failed to update API: ${e}`);
    } finally {
      setApiLoading(false);
    }
  };

  const handlePortApply = async () => {
    const port = parseInt(apiPort, 10);
    if (isNaN(port) || port < 1024 || port > 65535) {
      toast.error('Port must be between 1024 and 65535');
      return;
    }
    if (port === apiSettings.port) return;
    setApiLoading(true);
    try {
      const result = await invoke<ApiSettings>('cmd_update_api_settings', {
        enabled: apiSettings.enabled,
        port,
      });
      setApiSettings(result);
      toast.success(`API port updated to ${port}`);
    } catch (e) {
      toast.error(`Failed to update port: ${e}`);
    } finally {
      setApiLoading(false);
    }
  };

  const handleGenerateKey = async () => {
    const ok = await confirm({
      title: 'Generate API Key',
      message: apiSettings.key_set
        ? 'This will revoke your current API key and generate a new one. Any existing integrations will stop working.'
        : 'Generate a new API key for authenticating REST API requests.',
      confirmText: apiSettings.key_set ? 'Regenerate' : 'Generate',
      variant: apiSettings.key_set ? 'danger' : 'info',
    });
    if (!ok) return;
    try {
      const key = await invoke<string>('cmd_regenerate_api_key');
      setGeneratedKey(key);
      setKeyCopied(false);
      setApiSettings((prev) => ({ ...prev, key_set: true }));
      toast.success('API key generated');
    } catch (e) {
      toast.error(`Failed to generate key: ${e}`);
    }
  };

  const handleCopyKey = async () => {
    if (!generatedKey) return;
    try {
      await navigator.clipboard.writeText(generatedKey);
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 2000);
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/55 backdrop-blur-[6px]"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 4 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            className="bg-canvas border-hairline flex h-[600px] w-full max-w-[700px] flex-col overflow-hidden rounded-2xl border shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-hairline px-6 py-4 bg-surface/30">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 p-2 rounded-lg">
                  <Settings2 className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h2 className="text-foreground font-semibold">Settings</h2>
                  <p className="text-slate text-xs">Configure your personal cloud experience</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="h-8 w-8 rounded-full hover:bg-white/5"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Content with Tabs */}
            <Tabs defaultValue="general" className="flex flex-1 overflow-hidden">
              {/* Sidebar Tabs List */}
              <div className="w-[180px] border-r border-hairline bg-surface/10 p-3">
                <TabsList className="flex h-full w-full flex-col gap-1 bg-transparent p-0">
                  <div className="space-y-1">
                    <TabsTrigger
                      value="general"
                      className="w-full justify-start gap-2 px-3 py-2 text-xs data-[state=active]:bg-white/5 data-[state=active]:text-foreground"
                    >
                      <Settings2 className="h-3.5 w-3.5" />
                      General
                    </TabsTrigger>
                    <TabsTrigger
                      value="transfers"
                      className="w-full justify-start gap-2 px-3 py-2 text-xs data-[state=active]:bg-white/5 data-[state=active]:text-foreground"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Transfers
                    </TabsTrigger>
                    <TabsTrigger
                      value="network"
                      className="w-full justify-start gap-2 px-3 py-2 text-xs data-[state=active]:bg-white/5 data-[state=active]:text-foreground"
                    >
                      <Globe className="h-3.5 w-3.5" />
                      Network & API
                    </TabsTrigger>
                    <TabsTrigger
                      value="system"
                      className="w-full justify-start gap-2 px-3 py-2 text-xs data-[state=active]:bg-white/5 data-[state=active]:text-foreground"
                    >
                      <Cpu className="h-3.5 w-3.5" />
                      System
                    </TabsTrigger>
                  </div>
                  
                  <div className="flex-1" />
                  
                  <Separator className="bg-hairline/50 my-2" />
                  
                  <TabsTrigger
                    value="about"
                    className="relative w-full justify-start gap-2 px-3 py-2 text-xs data-[state=active]:bg-white/5 data-[state=active]:text-foreground"
                  >
                    <Info className="h-3.5 w-3.5" />
                    About
                    {available && (
                      <span
                        className="ml-auto flex items-center gap-1.5"
                        aria-label="Update available"
                        title={`Update available: ${version ?? ''}`}
                      >
                        <span className="bg-primary text-on-primary rounded-full px-1.5 py-px text-[9px] font-semibold leading-none tracking-wide uppercase">
                          New
                        </span>
                        <span className="bg-primary relative inline-flex h-1.5 w-1.5 rounded-full">
                          <span className="bg-primary absolute inset-0 animate-ping rounded-full opacity-60" />
                        </span>
                      </span>
                    )}
                  </TabsTrigger>
                </TabsList>
              </div>

              {/* Tab Contents */}
              <div className="flex-1 overflow-y-auto custom-scrollbar bg-canvas/50">
                <div className="p-8 max-w-[480px] mx-auto">
                  
                  {/* General Tab */}
                  <TabsContent value="general" className="mt-0 space-y-6">
                    <div className="space-y-1">
                      <h3 className="text-sm font-medium text-foreground">General Settings</h3>
                      <p className="text-xs text-slate">Basic application behavior and interface preferences.</p>
                    </div>
                    
                    <Separator />
                    
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label className="text-sm font-medium">Automatic Updates</Label>
                          <p className="text-[11px] text-slate">Check for new versions on startup</p>
                        </div>
                        <Switch
                          checked={settings.autoUpdate}
                          onCheckedChange={(v) => updateSetting('autoUpdate', v)}
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label className="text-sm font-medium">Start Minimised</Label>
                          <p className="text-[11px] text-slate">Launch the app minimised to the taskbar</p>
                        </div>
                        <Switch
                          checked={settings.startMinimised}
                          onCheckedChange={(v) => updateSetting('startMinimised', v)}
                        />
                      </div>
                    </div>
                  </TabsContent>

                  {/* Transfers Tab */}
                  <TabsContent value="transfers" className="mt-0 space-y-8">
                    <div className="space-y-1">
                      <h3 className="text-sm font-medium text-foreground">Transfer Limits</h3>
                      <p className="text-xs text-slate">Control how many files are processed simultaneously.</p>
                    </div>

                    <div className="space-y-8 pt-4">
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <Label className="text-sm font-medium">Concurrent Uploads</Label>
                          <span className="text-xs font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">
                            {settings.maxConcurrentUploads}
                          </span>
                        </div>
                        <Slider
                          value={[settings.maxConcurrentUploads]}
                          min={1}
                          max={10}
                          step={1}
                          onValueChange={([val]) => updateSetting('maxConcurrentUploads', val)}
                        />
                        <p className="text-[11px] text-slate italic">Recommended: 3-5 for best stability.</p>
                      </div>

                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <Label className="text-sm font-medium">Concurrent Downloads</Label>
                          <span className="text-xs font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">
                            {settings.maxConcurrentDownloads}
                          </span>
                        </div>
                        <Slider
                          value={[settings.maxConcurrentDownloads]}
                          min={1}
                          max={10}
                          step={1}
                          onValueChange={([val]) => updateSetting('maxConcurrentDownloads', val)}
                        />
                      </div>
                    </div>
                  </TabsContent>

                  {/* Network & API Tab */}
                  <TabsContent value="network" className="mt-0 space-y-6">
                    <div className="space-y-1">
                      <h3 className="text-sm font-medium text-foreground">REST API Server</h3>
                      <p className="text-xs text-slate">Expose a local API to integrate Telegrab with other tools.</p>
                    </div>

                    <Separator />

                    <div className="space-y-6 pt-2">
                      <div className="flex items-center justify-between p-4 rounded-xl bg-surface/40 border border-hairline">
                        <div className="space-y-1">
                          <Label className="text-sm font-medium">Server Status</Label>
                          <div className="flex items-center gap-2">
                            <span className={cn("h-1.5 w-1.5 rounded-full", apiSettings.running ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-zinc-600")} />
                            <span className="text-xs text-slate">{apiSettings.running ? "Active" : "Inactive"}</span>
                          </div>
                        </div>
                        <Switch 
                          checked={apiSettings.enabled}
                          onCheckedChange={handleApiToggle}
                          disabled={apiLoading}
                        />
                      </div>

                      <div className="grid gap-2">
                        <Label className="text-xs text-slate font-semibold uppercase tracking-wider">Configuration</Label>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 space-y-1.5">
                            <Label htmlFor="api-port" className="text-xs">Service Port</Label>
                            <Input
                              id="api-port"
                              type="number"
                              value={apiPort}
                              onChange={(e) => setApiPort(e.target.value)}
                              onBlur={handlePortApply}
                              className="h-9 text-sm bg-white/[0.02]"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3 pt-2">
                        <div className="flex items-center justify-between">
                           <Label className="text-xs text-slate font-semibold uppercase tracking-wider">Authentication</Label>
                           <Button
                              variant="link"
                              size="sm"
                              onClick={handleGenerateKey}
                              className="h-auto p-0 text-xs text-primary hover:text-primary-pressed"
                            >
                              {apiSettings.key_set ? "Regenerate Key" : "Generate Key"}
                            </Button>
                        </div>

                        {generatedKey ? (
                          <div className="bg-primary/5 rounded-lg border border-primary/20 p-3 space-y-2">
                            <p className="text-[10px] text-primary/80 font-medium">NEW API KEY (COPY NOW)</p>
                            <div className="flex items-center gap-2">
                              <code className="flex-1 text-[11px] font-mono bg-black/20 p-1.5 rounded truncate select-all">{generatedKey}</code>
                              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={handleCopyKey}>
                                {keyCopied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="p-3 rounded-lg border border-hairline bg-white/[0.02] text-center">
                            <p className="text-[11px] text-slate">
                              {apiSettings.key_set ? "API Key is configured and active." : "No API key configured. API requests will be unauthenticated."}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </TabsContent>

                  {/* System Tab */}
                  <TabsContent value="system" className="mt-0 space-y-6">
                    <div className="space-y-1">
                      <h3 className="text-sm font-medium text-foreground">System & Maintenance</h3>
                      <p className="text-xs text-slate">Manage local data and reset application state.</p>
                    </div>

                    <Separator />

                    <div className="space-y-4 pt-2">
                      <Card className="bg-surface/30 border-hairline hover:bg-surface/50 transition-colors">
                        <CardContent className="p-4 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
                              <Trash2 className="h-4 w-4" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">Local Cache</p>
                              <p className="text-[11px] text-slate">Previews and temporary files</p>
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={clearing}
                            onClick={async () => {
                              const ok = await confirm({
                                title: 'Clear Cache',
                                message: 'Remove all cached previews? This will not affect your Telegram files.',
                                confirmText: 'Clear',
                                variant: 'danger',
                              });
                              if (!ok) return;
                              setClearing(true);
                              try { await invoke('cmd_clean_cache'); toast.success('Cache cleared'); } 
                              catch { toast.error('Failed'); }
                              finally { setClearing(false); }
                            }}
                            className="h-8 text-xs border-rose-500/20 text-rose-400 hover:bg-rose-500/10"
                          >
                            {clearing ? "Clearing..." : "Clear Cache"}
                          </Button>
                        </CardContent>
                      </Card>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={resetSettings}
                        className="w-full justify-start gap-2 text-slate hover:text-foreground h-9"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Reset All Settings to Defaults
                      </Button>
                    </div>
                  </TabsContent>

                  {/* About Tab */}
                  <TabsContent value="about" className="mt-0 space-y-6">
                    <div className="flex flex-col items-center text-center space-y-3 py-8">
                      <h3 className="text-2xl font-bold text-foreground tracking-tight">Telegrab</h3>
                      <div className="px-3 py-0.5 bg-primary/10 rounded-full border border-primary/20">
                        <span className="text-[10px] font-bold text-primary uppercase tracking-widest">
                          Version {APP_VERSION}
                        </span>
                      </div>
                      <p className="text-sm text-slate">Professional Cloud Management for Telegram</p>
                    </div>

                    <Card className="bg-surface/30 border-hairline">
                      <CardContent className="p-4 space-y-3">
                        {/* State: checking */}
                        {checking && (
                          <div className="flex items-center gap-3">
                            <RefreshCw className="text-slate h-4 w-4 animate-spin" />
                            <div className="space-y-0.5">
                              <p className="text-sm font-medium">Checking for updates…</p>
                              <p className="text-[11px] text-slate">
                                Talking to the release server.
                              </p>
                            </div>
                          </div>
                        )}

                        {/* State: up to date */}
                        {!checking && !available && (
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                              <div className="space-y-0.5">
                                <p className="text-sm font-medium">You're up to date</p>
                                <p className="text-[11px] text-slate">
                                  Telegrab v{APP_VERSION} is the latest version.
                                </p>
                              </div>
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={checkForUpdates}
                              className="h-8 text-xs"
                            >
                              <RefreshCw className="mr-1.5 h-3 w-3" />
                              Check again
                            </Button>
                          </div>
                        )}

                        {/* State: update available */}
                        {!checking && available && (
                          <>
                            <div className="flex items-center gap-3">
                              <ArrowUpCircle className="text-primary h-4 w-4" />
                              <div className="space-y-0.5">
                                <p className="text-sm font-medium">
                                  New version {version} is available
                                </p>
                                <p className="text-[11px] text-slate">
                                  Download the installer and Telegrab will restart automatically.
                                </p>
                              </div>
                            </div>
                            <Button
                              onClick={downloadAndInstall}
                              disabled={downloading}
                              className="bg-primary text-on-primary hover:bg-primary-pressed h-9 w-full"
                            >
                              <Download className="mr-2 h-4 w-4" />
                              {downloading ? 'Downloading…' : `Update to ${version}`}
                            </Button>
                            {downloading && (
                              <div className="space-y-1.5">
                                <div className="bg-primary/10 h-1.5 overflow-hidden rounded-full">
                                  <motion.div
                                    className="bg-primary h-full"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${progress}%` }}
                                    transition={{ duration: 0.2, ease: 'linear' }}
                                  />
                                </div>
                                <p className="text-slate text-center text-[10px]">
                                  Downloading… {progress}%
                                </p>
                              </div>
                            )}
                          </>
                        )}
                      </CardContent>
                    </Card>

                    <Separator />

                    <div className="flex items-center justify-between pt-2">
                      <p className="text-xs text-slate">
                        Made by <span className="text-foreground font-medium">Jithin</span>
                      </p>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => shellOpen('https://github.com/jithin-jz')}
                          className="text-slate hover:text-foreground transition-colors p-1.5 rounded-md hover:bg-white/5"
                          title="GitHub"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                        </button>
                        <button
                          onClick={() => shellOpen('https://www.linkedin.com/in/jithin-kr')}
                          className="text-slate hover:text-foreground transition-colors p-1.5 rounded-md hover:bg-white/5"
                          title="LinkedIn"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                        </button>
                        <button
                          onClick={() => shellOpen('https://www.instagram.com/jithin.jz/')}
                          className="text-slate hover:text-foreground transition-colors p-1.5 rounded-md hover:bg-white/5"
                          title="Instagram"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
                        </button>
                      </div>
                    </div>

                    <p className="text-[10px] text-slate/40 text-center">
                      © 2026 Telegrab · Built for performance and privacy.
                    </p>
                  </TabsContent>

                </div>
              </div>
            </Tabs>

            {/* Footer */}
            <div className="border-t border-hairline px-6 py-4 flex justify-end bg-surface/30">
              <Button onClick={onClose} size="sm" className="h-9 px-8 rounded-lg shadow-lg shadow-primary/20">
                Done
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
