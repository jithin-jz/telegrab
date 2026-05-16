import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { motion, AnimatePresence } from "framer-motion";
import { Phone, Key, Lock, ArrowRight, Settings, ShieldCheck, HelpCircle, ExternalLink, QrCode, AlertCircle, Cloud, Zap, Shield } from "lucide-react";
import { load } from '@tauri-apps/plugin-store';
import { open } from '@tauri-apps/plugin-shell';
import { QRCodeSVG } from 'qrcode.react';

import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Alert, AlertDescription } from "./ui/alert";
import { Card, CardContent } from "./ui/card";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "./ui/dialog";
import logoUrl from "../assets/logo.svg";

type Step = "setup" | "phone" | "code" | "password";

export function AuthWizard({ onLogin }: { onLogin: () => void }) {
    const isBrowser = typeof window !== 'undefined' && !('__TAURI_INTERNALS__' in window);

    if (isBrowser) {
        return (
            <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto p-8 text-center">
                <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mb-6">
                    <ShieldCheck className="w-10 h-10 text-red-500" />
                </div>
                <h1 className="text-2xl font-bold text-white mb-4">Desktop App Required</h1>
                <p className="text-gray-400 mb-6 leading-relaxed">
                    You are viewing the internal development server in a browser.
                    This application cannot function here because it requires access to the system backend (Rust).
                </p>
                <div className="p-4 bg-gray-800 rounded-xl border border-gray-700 text-sm text-gray-300">
                    Please open the <strong>Telegrab</strong> window in your OS taskbar/dock to continue.
                </div>
            </div>
        )
    }

    const [step, setStep] = useState<Step>("setup");
    const [loading, setLoading] = useState(false);

    const [apiId, setApiId] = useState("");
    const [apiHash, setApiHash] = useState("");

    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [floodWait, setFloodWait] = useState<number | null>(null);
    const [showHelp, setShowHelp] = useState(false);
    const [loginMethod, setLoginMethod] = useState<'phone' | 'qr'>('phone');
    const [qrUrl, setQrUrl] = useState<string | null>(null);
    const [qrPolling, setQrPolling] = useState(false);
    const qrPollRef = useRef<ReturnType<typeof setInterval> | null>(null);


    useEffect(() => {
        if (!floodWait) return;
        const interval = setInterval(() => {
            setFloodWait(prev => {
                if (prev === null || prev <= 1) return null;
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(interval);
    }, [floodWait]);

    useEffect(() => {
        const initStore = async () => {
            try {
                const store = await load('config.json');
                const savedId = await store.get<string>('api_id');
                const savedHash = await store.get<string>('api_hash');

                if (savedId && savedHash) {
                    setApiId(savedId);
                    setApiHash(savedHash);
                }
            } catch {
                // config not found, starting fresh
            }
        };
        initStore();
    }, []);

    const saveCredentials = async () => {
        try {
            const store = await load('config.json');
            await store.set('api_id', apiId);
            await store.set('api_hash', apiHash);
            await store.save();
        } catch {
            // store write failure, non-critical
        }
    };

    const handleSetupSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (apiId.includes(' ') || apiHash.includes(' ')) {
            setError("API ID and API Hash cannot contain spaces. Please remove any spaces.");
            return;
        }

        if (!apiId || !apiHash) {
            setError("Both API ID and Hash are required.");
            return;
        }
        setError(null);
        await saveCredentials();
        setStep("phone");
        setLoginMethod('phone');
        setQrUrl(null);
        setQrPolling(false);
    };

    const handleQrLogin = async () => {
        setError(null);
        setLoading(true);
        try {
            const idInt = parseInt(apiId, 10);
            if (isNaN(idInt)) throw new Error("API ID must be a number");

            const url = await invoke<string>("cmd_auth_qr_login", {
                apiId: idInt,
                apiHash: apiHash
            });

            if (url === "__authorized__") {
                onLogin();
                return;
            }

            setQrUrl(url);
            setQrPolling(true);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setLoading(false);
        }
    };

    // QR polling effect
    useEffect(() => {
        if (!qrPolling) {
            if (qrPollRef.current) {
                clearInterval(qrPollRef.current);
                qrPollRef.current = null;
            }
            return;
        }

        qrPollRef.current = setInterval(async () => {
            try {
                const res = await invoke<{ success: boolean; next_step?: string }>("cmd_auth_qr_poll");
                if (res.success) {
                    setQrPolling(false);
                    if (res.next_step === "password") {
                        setStep("password");
                    } else {
                        onLogin();
                    }
                }
                // If next_step === "waiting", keep polling
            } catch {
                // Polling error — keep trying silently
            }
        }, 3000);

        return () => {
            if (qrPollRef.current) {
                clearInterval(qrPollRef.current);
                qrPollRef.current = null;
            }
        };
    }, [qrPolling, apiId, apiHash]);

    const handlePhoneSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const idInt = parseInt(apiId, 10);
            if (isNaN(idInt)) throw new Error("API ID must be a number");

            await invoke("cmd_auth_request_code", {
                phone,
                apiId: idInt,
                apiHash: apiHash
            });
            setStep("code");
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : JSON.stringify(err);
            if (msg.includes("FLOOD_WAIT_")) {
                const parts = msg.split("FLOOD_WAIT_");
                if (parts[1]) {
                    const seconds = parseInt(parts[1]);
                    if (!isNaN(seconds)) {
                        setFloodWait(seconds);
                        return;
                    }
                }
            }
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const handleCodeSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const res = await invoke<{ success: boolean; next_step?: string }>("cmd_auth_sign_in", { code });
            if (res.success) {
                onLogin();
            } else if (res.next_step === "password") {
                setStep("password");
            } else {
                setError("Unknown error");
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setLoading(false);
        }
    };

    const handlePasswordSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const res = await invoke<{ success: boolean; next_step?: string }>("cmd_auth_check_password", { password });
            if (res.success) {
                onLogin();
            } else {
                setError("Password verification failed.");
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-full w-full auth-gradient flex items-center justify-center p-6 relative">
            <div className="landing-split">
                {/* ── LEFT: Project Info ── */}
                <motion.div
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6 }}
                    className="landing-left"
                >
                    <div className="landing-left-inner">
                        <div className="flex items-center gap-3 mb-8">
                            <img src={logoUrl} alt="Telegrab" className="w-11 h-11 drop-shadow-lg" />
                            <span className="text-2xl font-bold text-white tracking-tight">Telegrab</span>
                        </div>

                        <h2 className="t-h2 text-white mb-4" style={{fontSize:'36px'}}>Your files,<br/>your cloud.</h2>
                        <p className="t-body text-white/60 mb-10 max-w-sm leading-relaxed">
                            Turn your Telegram account into unlimited personal cloud storage. Upload, organise and stream any file — encrypted, private and completely free.
                        </p>

                        <div className="space-y-5">
                            <div className="flex items-start gap-3">
                                <div className="w-9 h-9 rounded-xl bg-white/[0.06] flex items-center justify-center shrink-0 mt-0.5"><Cloud className="w-4 h-4 text-primary" /></div>
                                <div><p className="text-sm font-semibold text-white">Unlimited Storage</p><p className="text-xs text-white/40 mt-0.5">No caps — Telegram gives you infinite space for free.</p></div>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-9 h-9 rounded-xl bg-white/[0.06] flex items-center justify-center shrink-0 mt-0.5"><Shield className="w-4 h-4 text-primary" /></div>
                                <div><p className="text-sm font-semibold text-white">End-to-End Private</p><p className="text-xs text-white/40 mt-0.5">All data stays in your Telegram Saved Messages.</p></div>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-9 h-9 rounded-xl bg-white/[0.06] flex items-center justify-center shrink-0 mt-0.5"><Zap className="w-4 h-4 text-primary" /></div>
                                <div><p className="text-sm font-semibold text-white">Blazing Fast</p><p className="text-xs text-white/40 mt-0.5">Multi-part parallel uploads for maximum speed.</p></div>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* ── RIGHT: Login Card ── */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, delay: 0.15 }}
                    className="auth-glass p-8 rounded-3xl shadow-2xl w-full max-w-md landing-right"
                >
                    <div className="text-center mb-8">
                        <h1 className="text-xl font-bold text-white mb-1 tracking-tight">Get Started</h1>
                        <p className="text-sm text-white/60 font-medium">Connect your Telegram API</p>
                    </div>

                <AnimatePresence mode="wait">
                    {floodWait ? (
                        <motion.div
                            key="flood"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-center space-y-6"
                        >
                            <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto animate-pulse">
                                <span className="text-2xl">⏳</span>
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-white mb-2">Too Many Requests</h2>
                                <p className="text-sm text-gray-400">Telegram has temporarily limited your actions.</p>
                                <p className="text-sm text-gray-400">Please wait before trying again.</p>
                            </div>

                            <div className="text-5xl font-mono items-center justify-center flex text-blue-400 font-bold">
                                {Math.floor(floodWait / 60)}:{(floodWait % 60).toString().padStart(2, '0')}
                            </div>

                            <p className="text-xs text-red-400/60 mt-4">
                                Do not restart the app. The timer will reset if you do.
                            </p>
                        </motion.div>
                    ) : (
                        <>


                            {step === "setup" && (
                                <motion.form
                                    key="setup"
                                    initial={{ x: 20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    exit={{ x: -20, opacity: 0 }}
                                    onSubmit={handleSetupSubmit}
                                    className="space-y-5"
                                >
                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="api-id" className="text-xs font-semibold uppercase tracking-wider text-slate">
                                                API ID
                                            </Label>
                                            <div className="relative">
                                                <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone pointer-events-none" />
                                                <Input
                                                    id="api-id"
                                                    type="text"
                                                    value={apiId}
                                                    onChange={(e) => setApiId(e.target.value)}
                                                    placeholder="12345678"
                                                    className="pl-10 font-mono"
                                                    autoComplete="off"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="api-hash" className="text-xs font-semibold uppercase tracking-wider text-slate">
                                                API Hash
                                            </Label>
                                            <div className="relative">
                                                <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone pointer-events-none" />
                                                <Input
                                                    id="api-hash"
                                                    type="text"
                                                    value={apiHash}
                                                    onChange={(e) => setApiHash(e.target.value)}
                                                    placeholder="abcdef123456…"
                                                    className="pl-10 font-mono"
                                                    autoComplete="off"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    <Button type="submit" size="lg" className="w-full">
                                        Configure
                                        <Settings className="w-4 h-4" />
                                    </Button>

                                    <Button
                                        type="button"
                                        variant="link"
                                        size="sm"
                                        onClick={() => setShowHelp(true)}
                                        className="w-full text-xs"
                                    >
                                        <HelpCircle className="w-3 h-3" />
                                        How do I get my API credentials?
                                    </Button>

                                    {import.meta.env.DEV && (
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => onLogin()}
                                            className="w-full text-xs text-destructive/80 hover:text-destructive"
                                        >
                                            Dev Mode
                                        </Button>
                                    )}
                                </motion.form>
                            )}


                            {step === "phone" && (
                                <motion.div
                                    key="phone"
                                    initial={{ x: 20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    exit={{ x: -20, opacity: 0 }}
                                    className="space-y-6"
                                >
                                    {/* Phone / QR Toggle */}
                                    <div className="flex rounded-xl overflow-hidden border border-white/10">
                                        <button
                                            type="button"
                                            onClick={() => { setLoginMethod('phone'); setQrUrl(null); setQrPolling(false); setError(null); }}
                                            className={`flex-1 py-2.5 text-sm font-medium flex items-center justify-center gap-2 transition-all ${
                                                loginMethod === 'phone'
                                                    ? 'bg-white/15 text-white'
                                                    : 'text-white/50 hover:text-white/70'
                                            }`}
                                        >
                                            <Phone className="w-4 h-4" /> Phone Number
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => { setLoginMethod('qr'); setError(null); handleQrLogin(); }}
                                            className={`flex-1 py-2.5 text-sm font-medium flex items-center justify-center gap-2 transition-all ${
                                                loginMethod === 'qr'
                                                    ? 'bg-white/15 text-white'
                                                    : 'text-white/50 hover:text-white/70'
                                            }`}
                                        >
                                            <QrCode className="w-4 h-4" /> QR Code
                                        </button>
                                    </div>

                                    {loginMethod === 'phone' ? (
                                        <form onSubmit={handlePhoneSubmit} className="space-y-6">
                                            <div className="space-y-2">
                                                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider">Phone Number</label>
                                                <div className="relative">
                                                    <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 auth-form-icon" />
                                                    <input
                                                        type="tel"
                                                        value={phone}
                                                        onChange={(e) => setPhone(e.target.value)}
                                                        placeholder="+1 234 567 8900"
                                                        className="w-full glass-input rounded-xl pl-12 pr-4 py-4 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-all text-lg tracking-wide"
                                                    />
                                                </div>
                                            </div>

                                            <div className="flex flex-col gap-3">
                                                <button
                                                    type="submit"
                                                    disabled={loading}
                                                    className="w-full bg-white text-black hover:bg-gray-100 font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                                                >
                                                    {loading ? "Connecting..." : <>Continue <ArrowRight className="w-5 h-5" /></>}
                                                </button>
                                                <button type="button" onClick={() => setStep("setup")} className="text-xs text-gray-500 hover:text-white transition-colors py-2">
                                                    Back to Configuration
                                                </button>
                                            </div>
                                        </form>
                                    ) : (
                                        <div className="flex flex-col items-center gap-5">
                                            {loading && !qrUrl && (
                                                <div className="w-52 h-52 rounded-2xl bg-white/5 flex items-center justify-center">
                                                    <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                                                </div>
                                            )}
                                            {qrUrl && (
                                                <>
                                                    <div className="p-4 bg-white rounded-2xl shadow-xl">
                                                        <QRCodeSVG
                                                            value={qrUrl}
                                                            size={200}
                                                            level="M"
                                                            bgColor="#ffffff"
                                                            fgColor="#000000"
                                                        />
                                                    </div>
                                                    <div className="text-center space-y-1">
                                                        <p className="text-sm text-white/80">Scan with your Telegram app</p>
                                                        <p className="text-xs text-white/40">Settings &gt; Devices &gt; Link Desktop Device</p>
                                                    </div>
                                                    {qrPolling && (
                                                        <div className="flex items-center gap-2 text-xs text-blue-300">
                                                            <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                                                            Waiting for scan...
                                                        </div>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={handleQrLogin}
                                                        className="text-xs text-white/50 hover:text-white transition-colors"
                                                    >
                                                        Refresh QR Code
                                                    </button>
                                                </>
                                            )}
                                            <button type="button" onClick={() => { setStep("setup"); setQrPolling(false); }} className="text-xs text-gray-500 hover:text-white transition-colors py-2">
                                                Back to Configuration
                                            </button>
                                        </div>
                                    )}
                                </motion.div>
                            )}


                            {step === "code" && (
                                <motion.form
                                    key="code"
                                    initial={{ x: 20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    exit={{ x: -20, opacity: 0 }}
                                    onSubmit={handleCodeSubmit}
                                    className="space-y-6"
                                >
                                    <div className="space-y-2">
                                        <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider">Telegram Code</label>
                                        <div className="relative">
                                            <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 auth-form-icon" />
                                            <input
                                                type="text"
                                                value={code}
                                                onChange={(e) => setCode(e.target.value)}
                                                placeholder="1 2 3 4 5"
                                                className="w-full glass-input rounded-xl pl-12 pr-4 py-4 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-all text-2xl tracking-[0.5em] font-mono text-center"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-3">
                                        <button
                                            type="submit"
                                            disabled={loading}
                                            className="w-full bg-white text-black hover:bg-gray-100 font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg active:scale-[0.98]"
                                        >
                                            {loading ? "Verifying..." : "Sign In"}
                                        </button>
                                        <button type="button" onClick={() => setStep("phone")} className="text-xs text-gray-500 hover:text-white transition-colors py-2">
                                            Change Phone Number
                                        </button>
                                    </div>
                                </motion.form>
                            )}


                            {step === "password" && (
                                <motion.form
                                    key="password"
                                    initial={{ x: 20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    exit={{ x: -20, opacity: 0 }}
                                    onSubmit={handlePasswordSubmit}
                                    className="space-y-6"
                                >
                                    <div className="space-y-2">
                                        <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl mb-4">
                                            <p className="text-xs text-blue-300 text-center">
                                                Your account has Two-Factor Authentication enabled.
                                                Please enter your cloud password to continue.
                                            </p>
                                        </div>
                                        <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider">Cloud Password</label>
                                        <div className="relative">
                                            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 auth-form-icon" />
                                            <input
                                                type="password"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                placeholder="Enter your password"
                                                className="w-full glass-input rounded-xl pl-12 pr-4 py-4 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-all text-lg"
                                                autoFocus
                                            />
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-3">
                                        <button
                                            type="submit"
                                            disabled={loading || !password}
                                            className="w-full bg-white text-black hover:bg-gray-100 font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {loading ? "Verifying..." : "Unlock"}
                                        </button>
                                        <button type="button" onClick={() => { setStep("code"); setPassword(""); setError(null); }} className="text-xs text-gray-500 hover:text-white transition-colors py-2">
                                            Back to Code Entry
                                        </button>
                                    </div>
                                </motion.form>
                            )}
                        </>
                    )}
                </AnimatePresence>

                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-6"
                    >
                        <Alert variant="destructive">
                            <AlertCircle className="w-4 h-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    </motion.div>
                )}
                </motion.div>
            </div>


            <Dialog open={showHelp} onOpenChange={setShowHelp}>
                <DialogContent className="max-w-md gap-0 overflow-hidden p-0">
                    <DialogHeader className="border-b border-hairline px-5 py-4">
                        <DialogTitle>Getting started</DialogTitle>
                        <DialogDescription>
                            You only need a Telegram API ID and API Hash.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-3 px-5 py-4">
                        <Alert className="border-primary/20 bg-primary/10">
                            <HelpCircle className="h-4 w-4 text-primary" />
                            <AlertDescription className="text-slate">
                                Credentials stay on this device and are used only to connect your Telegram account.
                            </AlertDescription>
                        </Alert>

                        <HelpStep number="1" title="Open the developer portal">
                            Sign in at <button type="button" onClick={() => open('https://my.telegram.org')} className="text-primary hover:underline">my.telegram.org</button>.
                        </HelpStep>

                        <HelpStep number="2" title="Create an app">
                            Choose <span className="font-medium text-foreground">API development tools</span>, then create any app name.
                        </HelpStep>

                        <HelpStep number="3" title="Paste both values">
                            Copy the <span className="font-medium text-foreground">API ID</span> and <span className="font-medium text-foreground">API Hash</span> into Telegrab.
                        </HelpStep>
                    </div>

                    <DialogFooter className="border-t border-hairline px-5 py-4">
                        <DialogClose asChild>
                            <Button type="button" variant="outline">
                                Done
                            </Button>
                        </DialogClose>
                        <Button
                            type="button"
                            onClick={() => open('https://my.telegram.org')}
                        >
                            Open portal
                            <ExternalLink className="h-4 w-4" />
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <div className="fixed top-[-20%] left-[-10%] w-[500px] h-[500px] bg-blue-600/20 rounded-full blur-[120px] pointer-events-none -z-10" />
            <div className="fixed bottom-[-10%] right-[-10%] w-[400px] h-[400px] bg-purple-600/10 rounded-full blur-[100px] pointer-events-none -z-10" />
        </div>
    );
}

function HelpStep({
    number,
    title,
    children,
}: {
    number: string;
    title: string;
    children: React.ReactNode;
}) {
    return (
        <Card className="bg-surface/80">
            <CardContent className="flex gap-3 p-3">
                <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                    {number}
                </span>
                <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-foreground">{title}</h3>
                    <p className="mt-1 text-sm leading-5 text-slate">{children}</p>
                </div>
            </CardContent>
        </Card>
    );
}
