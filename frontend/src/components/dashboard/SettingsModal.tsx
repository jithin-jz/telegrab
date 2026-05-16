import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, RotateCcw, Download, Upload, Trash2, HardDrive, Globe, Key, Copy, Check, RefreshCw } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import { useSettings } from '../../contexts/SettingsContext';
import { useConfirm } from '../../contexts/ConfirmContext';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Input } from '../ui/input';

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
    const [clearing, setClearing] = useState(false);

    // API settings state
    const [apiSettings, setApiSettings] = useState<ApiSettings>({ enabled: false, port: 8550, key_set: false, running: false });
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

    // Load API settings when modal opens
    useEffect(() => {
        if (isOpen) {
            fetchApiSettings();
            setGeneratedKey(null);
            setKeyCopied(false);
        }
    }, [isOpen, fetchApiSettings]);

    // Poll API status while modal is open and API is enabled
    useEffect(() => {
        if (!isOpen || !apiSettings.enabled) return;
        const interval = setInterval(fetchApiSettings, 3000);
        return () => clearInterval(interval);
    }, [isOpen, apiSettings.enabled, fetchApiSettings]);

    const handleApiToggle = async () => {
        setApiLoading(true);
        try {
            const port = parseInt(apiPort, 10);
            if (isNaN(port) || port < 1024 || port > 65535) {
                toast.error('Port must be between 1024 and 65535');
                setApiLoading(false);
                return;
            }
            const result = await invoke<ApiSettings>('cmd_update_api_settings', {
                enabled: !apiSettings.enabled,
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
            setApiSettings(prev => ({ ...prev, key_set: true }));
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
                    className="fixed inset-0 z-[120] flex justify-end bg-black/45 backdrop-blur-[2px]"
                    onClick={onClose}
                >
                    <motion.aside
                        initial={{ x: 480 }}
                        animate={{ x: 0 }}
                        exit={{ x: 480 }}
                        transition={{ type: 'spring', damping: 32, stiffness: 360 }}
                        className="h-full w-full max-w-[460px] bg-canvas border-l border-hairline shadow-2xl overflow-hidden flex flex-col"
                        onClick={e => e.stopPropagation()}
                        role="dialog"
                        aria-modal="true"
                        aria-label="Settings"
                    >
                        {/* Header */}
                        <div className="px-5 py-4 border-b border-hairline flex justify-between items-start gap-4 bg-surface/80">
                            <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                    <h2 className="text-telegram-text font-semibold text-base">Settings</h2>
                                    <span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_8px_rgba(70,194,100,0.55)]" />
                                </div>
                                <p className="text-xs text-stone mt-1">Tune transfers, API access, and local storage.</p>
                            </div>
                            <button
                                onClick={onClose}
                                className="w-8 h-8 grid place-items-center hover:bg-white/[0.04] rounded-md text-telegram-subtext hover:text-telegram-text transition"
                                aria-label="Close settings"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Body */}
                        <div className="flex-1 px-5 py-5 space-y-5 overflow-y-auto custom-scrollbar">

                            {/* Transfers Section */}
                            <section className="space-y-3">
                                <h3 className="text-xs font-semibold text-telegram-subtext uppercase tracking-wider flex items-center gap-2">
                                    <Upload className="w-3.5 h-3.5" />
                                    Transfers
                                </h3>

                                {/* Max Concurrent Uploads */}
                                <Card className="bg-surface">
                                    <CardContent className="flex items-center justify-between gap-4 p-3">
                                    <div className="flex items-center gap-2">
                                        <Upload className="w-4 h-4 text-telegram-subtext" />
                                        <div>
                                            <p className="text-sm text-telegram-text font-medium">Concurrent Uploads</p>
                                            <p className="text-xs text-telegram-subtext">Max parallel uploads</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="icon"
                                            onClick={() => updateSetting('maxConcurrentUploads', Math.max(1, settings.maxConcurrentUploads - 1))}
                                            className="h-7 w-7 text-sm text-telegram-subtext hover:text-telegram-text"
                                        >
                                            -
                                        </Button>
                                        <span className="text-sm text-telegram-text font-medium w-5 text-center">
                                            {settings.maxConcurrentUploads}
                                        </span>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="icon"
                                            onClick={() => updateSetting('maxConcurrentUploads', Math.min(10, settings.maxConcurrentUploads + 1))}
                                            className="h-7 w-7 text-sm text-telegram-subtext hover:text-telegram-text"
                                        >
                                            +
                                        </Button>
                                    </div>
                                    </CardContent>
                                </Card>

                                {/* Max Concurrent Downloads */}
                                <Card className="bg-surface">
                                    <CardContent className="flex items-center justify-between gap-4 p-3">
                                    <div className="flex items-center gap-2">
                                        <Download className="w-4 h-4 text-telegram-subtext" />
                                        <div>
                                            <p className="text-sm text-telegram-text font-medium">Concurrent Downloads</p>
                                            <p className="text-xs text-telegram-subtext">Max parallel downloads</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="icon"
                                            onClick={() => updateSetting('maxConcurrentDownloads', Math.max(1, settings.maxConcurrentDownloads - 1))}
                                            className="h-7 w-7 text-sm text-telegram-subtext hover:text-telegram-text"
                                        >
                                            -
                                        </Button>
                                        <span className="text-sm text-telegram-text font-medium w-5 text-center">
                                            {settings.maxConcurrentDownloads}
                                        </span>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="icon"
                                            onClick={() => updateSetting('maxConcurrentDownloads', Math.min(10, settings.maxConcurrentDownloads + 1))}
                                            className="h-7 w-7 text-sm text-telegram-subtext hover:text-telegram-text"
                                        >
                                            +
                                        </Button>
                                    </div>
                                    </CardContent>
                                </Card>
                            </section>

                            {/* REST API Section */}
                            <section className="space-y-3">
                                <h3 className="text-xs font-semibold text-telegram-subtext uppercase tracking-wider flex items-center gap-2">
                                    <Globe className="w-3.5 h-3.5" />
                                    REST API
                                </h3>

                                {/* Enable Toggle */}
                                <Card className="bg-surface">
                                    <CardContent className="flex items-center justify-between gap-4 p-3">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-2 h-2 rounded-full ${apiSettings.running ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]' : 'bg-gray-500'}`} />
                                        <div>
                                            <p className="text-sm text-telegram-text font-medium">Enable API Server</p>
                                            <p className="text-xs text-telegram-subtext">
                                                {apiSettings.running ? `Running on port ${apiSettings.port}` : 'Localhost only (127.0.0.1)'}
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={handleApiToggle}
                                        disabled={apiLoading}
                                        className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${apiSettings.enabled ? 'bg-telegram-primary' : 'bg-telegram-border'} disabled:opacity-50 shrink-0`}
                                        aria-label={apiSettings.enabled ? 'Disable API server' : 'Enable API server'}
                                    >
                                        <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ${apiSettings.enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                    </button>
                                    </CardContent>
                                </Card>

                                {/* Port */}
                                <Card className="bg-surface">
                                    <CardContent className="flex items-center justify-between gap-4 p-3">
                                    <div>
                                        <p className="text-sm text-telegram-text font-medium">Port</p>
                                        <p className="text-xs text-telegram-subtext">1024 - 65535</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Input
                                            type="number"
                                            min="1024"
                                            max="65535"
                                            value={apiPort}
                                            onChange={e => setApiPort(e.target.value)}
                                            onBlur={handlePortApply}
                                            onKeyDown={e => { if (e.key === 'Enter') handlePortApply(); }}
                                            className="h-8 w-24 text-center"
                                        />
                                    </div>
                                    </CardContent>
                                </Card>

                                {/* API Key */}
                                <Card className="bg-surface">
                                    <CardContent className="space-y-2.5 p-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Key className="w-4 h-4 text-telegram-subtext" />
                                            <div>
                                                <p className="text-sm text-telegram-text font-medium">API Key</p>
                                                <p className="text-xs text-telegram-subtext">
                                                    {apiSettings.key_set ? 'Key configured' : 'No key set'}
                                                </p>
                                            </div>
                                        </div>
                                        <Button
                                            type="button"
                                            variant="secondary"
                                            size="sm"
                                            onClick={handleGenerateKey}
                                            className="h-8 shrink-0 text-xs text-telegram-primary"
                                        >
                                            <RefreshCw className="w-3 h-3" />
                                            {apiSettings.key_set ? 'Regenerate' : 'Generate'}
                                        </Button>
                                    </div>

                                    {/* One-time key reveal */}
                                    {generatedKey && (
                                        <div className="mt-2 p-2.5 bg-canvas rounded-lg border border-yellow-500/20">
                                            <p className="text-[10px] text-yellow-400/80 uppercase tracking-wider font-semibold mb-1.5">
                                                Copy now - this key will not be shown again
                                            </p>
                                            <div className="flex items-center gap-2">
                                                <code className="flex-1 text-xs text-telegram-text font-mono bg-telegram-hover rounded px-2 py-1.5 overflow-x-auto select-all">
                                                    {generatedKey}
                                                </code>
                                                <button
                                                    onClick={handleCopyKey}
                                                    className="p-1.5 rounded-md hover:bg-telegram-hover text-telegram-subtext hover:text-telegram-text transition flex-shrink-0"
                                                    title="Copy to clipboard"
                                                >
                                                    {keyCopied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                    </CardContent>
                                </Card>
                            </section>

                            {/* Storage Section */}
                            <section className="space-y-3">
                                <h3 className="text-xs font-semibold text-telegram-subtext uppercase tracking-wider flex items-center gap-2">
                                    <HardDrive className="w-3.5 h-3.5" />
                                    Storage
                                </h3>

                                <Card className="bg-surface">
                                    <CardContent className="flex items-center justify-between gap-4 p-3">
                                    <div className="flex items-center gap-2">
                                        <Trash2 className="w-4 h-4 text-telegram-subtext" />
                                        <div>
                                            <p className="text-sm text-telegram-text font-medium">Clear Local Cache</p>
                                            <p className="text-xs text-telegram-subtext">Remove cached previews and temp files</p>
                                        </div>
                                    </div>
                                    <Button
                                        type="button"
                                        variant="destructive"
                                        size="sm"
                                        disabled={clearing}
                                        onClick={async () => {
                                            const ok = await confirm({
                                                title: 'Clear Cache',
                                                message: 'This will remove all cached previews and temporary files. Your uploaded files on Telegram are not affected.',
                                                confirmText: 'Clear',
                                                variant: 'danger',
                                            });
                                            if (!ok) return;
                                            setClearing(true);
                                            try {
                                                await invoke('cmd_clean_cache');
                                                toast.success('Cache cleared successfully');
                                            } catch {
                                                toast.error('Failed to clear cache');
                                            } finally {
                                                setClearing(false);
                                            }
                                        }}
                                        className="h-8 shrink-0 bg-red-500/10 text-xs text-red-400 hover:bg-red-500/20"
                                    >
                                        {clearing ? 'Clearing...' : 'Clear'}
                                    </Button>
                                    </CardContent>
                                </Card>
                            </section>
                        </div>

                        {/* Footer */}
                        <div className="px-5 py-3 border-t border-hairline bg-surface/80 flex items-center justify-between gap-3">
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={resetSettings}
                                className="h-8 text-xs text-telegram-subtext hover:text-red-400 hover:bg-red-500/10"
                            >
                                <RotateCcw className="w-3.5 h-3.5" />
                                Reset to Defaults
                            </Button>
                            <Button
                                type="button"
                                size="sm"
                                onClick={onClose}
                                className="h-8 text-xs"
                            >
                                Done
                            </Button>
                        </div>
                    </motion.aside>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
