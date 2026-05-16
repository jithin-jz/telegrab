import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { motion, AnimatePresence } from "framer-motion";
import { Phone, Key, Lock, ArrowRight, ShieldCheck, HelpCircle, ExternalLink, QrCode, AlertCircle, Cloud, Zap, Shield } from "lucide-react";
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
            <div className="landing-split z-10 relative">
                {/* ── LEFT: Project Info ── */}
                <motion.div
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6 }}
                    className="landing-left"
                >
                    <div className="landing-left-inner relative">
                        <div className="flex items-center gap-3 mb-10">
                            <div className="p-2 rounded-2xl bg-gradient-to-tr from-primary/80 to-purple-400 shadow-[0_0_20px_rgba(124,92,255,0.4)]">
                                <img src={logoUrl} alt="Telegrab" className="w-8 h-8 drop-shadow-lg filter brightness-0 invert" />
                            </div>
                            <span className="text-3xl font-extrabold text-white tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">Telegrab</span>
                        </div>

                        <h2 className="text-5xl font-extrabold text-white mb-5 leading-[1.1] tracking-tight">Your files,<br/><span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-400">your cloud.</span></h2>
                        <p className="text-lg text-white/60 mb-12 max-w-sm leading-relaxed font-medium">
                            Turn your Telegram account into unlimited personal cloud storage. Upload, organise and stream any file — encrypted, private and completely free.
                        </p>

                        <div className="space-y-6">
                            <div className="flex items-start gap-4 group">
                                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/5 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 group-hover:border-primary/30 transition-all duration-300 shadow-[0_0_15px_rgba(0,0,0,0.2)]">
                                    <Cloud className="w-5 h-5 text-blue-400 group-hover:text-blue-300" />
                                </div>
                                <div><p className="text-base font-bold text-white mb-1">Unlimited Storage</p><p className="text-sm text-white/50 leading-relaxed">No caps — Telegram gives you infinite space for free.</p></div>
                            </div>
                            <div className="flex items-start gap-4 group">
                                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-white/5 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 group-hover:border-purple-400/30 transition-all duration-300 shadow-[0_0_15px_rgba(0,0,0,0.2)]">
                                    <Shield className="w-5 h-5 text-purple-400 group-hover:text-purple-300" />
                                </div>
                                <div><p className="text-base font-bold text-white mb-1">End-to-End Private</p><p className="text-sm text-white/50 leading-relaxed">All data stays in your Telegram Saved Messages.</p></div>
                            </div>
                            <div className="flex items-start gap-4 group">
                                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500/10 to-yellow-500/10 border border-white/5 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 group-hover:border-orange-400/30 transition-all duration-300 shadow-[0_0_15px_rgba(0,0,0,0.2)]">
                                    <Zap className="w-5 h-5 text-orange-400 group-hover:text-orange-300" />
                                </div>
                                <div><p className="text-base font-bold text-white mb-1">Blazing Fast</p><p className="text-sm text-white/50 leading-relaxed">Multi-part parallel uploads for maximum speed.</p></div>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* ── RIGHT: Login Card ── */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, delay: 0.15 }}
                    className="auth-glass p-10 rounded-[2rem] shadow-2xl w-full max-w-[440px] landing-right relative group before:absolute before:inset-0 before:-z-10 before:rounded-[2rem] before:bg-gradient-to-b before:from-white/10 before:to-transparent before:p-[1px] before:content-[''] before:[mask-composite:exclude] before:[mask-image:linear-gradient(#fff_0_0),linear-gradient(#fff_0_0)]"
                >
                    <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-b from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                    
                    <div className="text-center mb-10">
                        <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">Get Started</h1>
                        <p className="text-sm text-white/60 font-medium">Connect your Telegram API</p>
                    </div>

                <AnimatePresence mode="wait">
                    {floodWait ? (
                        <motion.div
                            key="flood"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-center space-y-6 relative z-10"
                        >
                            <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto animate-pulse shadow-[0_0_30px_rgba(239,68,68,0.3)]">
                                <AlertCircle className="w-10 h-10 text-red-500" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-white mb-2">Too Many Requests</h2>
                                <p className="text-sm text-gray-400">Telegram has temporarily limited your actions.</p>
                                <p className="text-sm text-gray-400">Please wait before trying again.</p>
                            </div>

                            <div className="text-5xl font-mono items-center justify-center flex text-blue-400 font-bold drop-shadow-[0_0_15px_rgba(96,165,250,0.5)]">
                                {Math.floor(floodWait / 60)}:{(floodWait % 60).toString().padStart(2, '0')}
                            </div>

                            <p className="text-xs text-red-400/60 mt-4 font-medium">
                                Do not restart the app. The timer will reset if you do.
                            </p>
                        </motion.div>
                    ) : (
                        <div className="relative z-10">


                            {step === "setup" && (
                                <motion.form
                                    key="setup"
                                    initial={{ x: 20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    exit={{ x: -20, opacity: 0 }}
                                    onSubmit={handleSetupSubmit}
                                    className="space-y-6"
                                >
                                    <div className="space-y-5">
                                        <div className="space-y-2">
                                            <Label htmlFor="api-id" className="text-[11px] font-bold uppercase tracking-widest text-slate ml-1">
                                                API ID
                                            </Label>
                                            <div className="relative group/input">
                                                <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate transition-colors group-focus-within/input:text-primary" />
                                                <Input
                                                    id="api-id"
                                                    type="text"
                                                    value={apiId}
                                                    onChange={(e) => setApiId(e.target.value)}
                                                    placeholder="12345678"
                                                    className="pl-11 h-12 bg-white/5 border-white/10 text-white placeholder:text-white/20 focus:bg-white/10 focus:border-primary/50 transition-all font-mono rounded-xl shadow-inner"
                                                    autoComplete="off"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="api-hash" className="text-[11px] font-bold uppercase tracking-widest text-slate ml-1">
                                                API Hash
                                            </Label>
                                            <div className="relative group/input">
                                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate transition-colors group-focus-within/input:text-primary" />
                                                <Input
                                                    id="api-hash"
                                                    type="text"
                                                    value={apiHash}
                                                    onChange={(e) => setApiHash(e.target.value)}
                                                    placeholder="abcdef123456…"
                                                    className="pl-11 h-12 bg-white/5 border-white/10 text-white placeholder:text-white/20 focus:bg-white/10 focus:border-primary/50 transition-all font-mono rounded-xl shadow-inner"
                                                    autoComplete="off"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    <button 
                                        type="submit" 
                                        className="w-full h-12 bg-gradient-to-r from-primary to-blue-500 hover:from-primary-pressed hover:to-blue-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-[0_0_20px_rgba(124,92,255,0.3)] hover:shadow-[0_0_25px_rgba(124,92,255,0.5)] active:scale-[0.98]"
                                    >
                                        Configure
                                        <ArrowRight className="w-4 h-4" />
                                    </button>

                                    <Button
                                        type="button"
                                        variant="link"
                                        size="sm"
                                        onClick={() => setShowHelp(true)}
                                        className="w-full text-xs text-white/40 hover:text-white/80 transition-colors"
                                    >
                                        <HelpCircle className="w-3 h-3 mr-1" />
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
                                    <div className="flex p-1 bg-white/5 rounded-xl border border-white/10">
                                        <button
                                            type="button"
                                            onClick={() => { setLoginMethod('phone'); setQrUrl(null); setQrPolling(false); setError(null); }}
                                            className={`flex-1 py-2 text-sm font-bold rounded-lg flex items-center justify-center gap-2 transition-all ${
                                                loginMethod === 'phone'
                                                    ? 'bg-white/10 text-white shadow-sm'
                                                    : 'text-white/40 hover:text-white/60'
                                            }`}
                                        >
                                            <Phone className="w-4 h-4" /> Phone Number
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => { setLoginMethod('qr'); setError(null); handleQrLogin(); }}
                                            className={`flex-1 py-2 text-sm font-bold rounded-lg flex items-center justify-center gap-2 transition-all ${
                                                loginMethod === 'qr'
                                                    ? 'bg-white/10 text-white shadow-sm'
                                                    : 'text-white/40 hover:text-white/60'
                                            }`}
                                        >
                                            <QrCode className="w-4 h-4" /> QR Code
                                        </button>
                                    </div>

                                    {loginMethod === 'phone' ? (
                                        <form onSubmit={handlePhoneSubmit} className="space-y-6">
                                            <div className="space-y-2">
                                                <label className="block text-[11px] font-bold text-slate uppercase tracking-widest ml-1">Phone Number</label>
                                                <div className="relative group/input">
                                                    <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate transition-colors group-focus-within/input:text-primary" />
                                                    <input
                                                        type="tel"
                                                        value={phone}
                                                        onChange={(e) => setPhone(e.target.value)}
                                                        placeholder="+1 234 567 8900"
                                                        className="w-full h-14 bg-white/5 border border-white/10 text-white placeholder:text-white/20 focus:bg-white/10 focus:border-primary/50 transition-all text-lg tracking-wider rounded-xl pl-12 pr-4 outline-none shadow-inner"
                                                    />
                                                </div>
                                            </div>

                                            <div className="flex flex-col gap-4">
                                                <button
                                                    type="submit"
                                                    disabled={loading}
                                                    className="w-full h-12 bg-gradient-to-r from-primary to-blue-500 hover:from-primary-pressed hover:to-blue-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-[0_0_20px_rgba(124,92,255,0.3)] hover:shadow-[0_0_25px_rgba(124,92,255,0.5)] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                                                >
                                                    {loading ? "Connecting..." : <>Continue <ArrowRight className="w-5 h-5" /></>}
                                                </button>
                                                <button type="button" onClick={() => setStep("setup")} className="text-xs font-medium text-white/40 hover:text-white/80 transition-colors py-2">
                                                    Back to Configuration
                                                </button>
                                            </div>
                                        </form>
                                    ) : (
                                        <div className="flex flex-col items-center gap-6">
                                            {loading && !qrUrl && (
                                                <div className="w-52 h-52 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center shadow-inner">
                                                    <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                                </div>
                                            )}
                                            {qrUrl && (
                                                <>
                                                    <div className="p-4 bg-white rounded-2xl shadow-[0_0_30px_rgba(255,255,255,0.2)]">
                                                        <QRCodeSVG
                                                            value={qrUrl}
                                                            size={200}
                                                            level="M"
                                                            bgColor="#ffffff"
                                                            fgColor="#000000"
                                                        />
                                                    </div>
                                                    <div className="text-center space-y-1.5">
                                                        <p className="text-sm font-medium text-white">Scan with your Telegram app</p>
                                                        <p className="text-xs text-white/50">Settings &gt; Devices &gt; Link Desktop Device</p>
                                                    </div>
                                                    {qrPolling && (
                                                        <div className="flex items-center justify-center gap-2 text-xs font-bold text-primary px-4 py-2 bg-primary/10 rounded-full">
                                                            <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                                            Waiting for scan...
                                                        </div>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={handleQrLogin}
                                                        className="text-xs font-medium text-white/40 hover:text-white/80 transition-colors"
                                                    >
                                                        Refresh QR Code
                                                    </button>
                                                </>
                                            )}
                                            <button type="button" onClick={() => { setStep("setup"); setQrPolling(false); }} className="text-xs font-medium text-white/40 hover:text-white/80 transition-colors py-2">
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
                                        <label className="block text-[11px] font-bold text-slate uppercase tracking-widest ml-1">Telegram Code</label>
                                        <div className="relative group/input">
                                            <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate transition-colors group-focus-within/input:text-primary" />
                                            <input
                                                type="text"
                                                value={code}
                                                onChange={(e) => setCode(e.target.value)}
                                                placeholder="1 2 3 4 5"
                                                className="w-full h-16 bg-white/5 border border-white/10 text-white placeholder:text-white/20 focus:bg-white/10 focus:border-primary/50 transition-all text-2xl tracking-[0.5em] font-mono text-center rounded-xl outline-none shadow-inner"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-4">
                                        <button
                                            type="submit"
                                            disabled={loading}
                                            className="w-full h-12 bg-gradient-to-r from-primary to-blue-500 hover:from-primary-pressed hover:to-blue-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-[0_0_20px_rgba(124,92,255,0.3)] hover:shadow-[0_0_25px_rgba(124,92,255,0.5)] active:scale-[0.98]"
                                        >
                                            {loading ? "Verifying..." : "Sign In"}
                                        </button>
                                        <button type="button" onClick={() => setStep("phone")} className="text-xs font-medium text-white/40 hover:text-white/80 transition-colors py-2">
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
                                        <div className="p-4 bg-primary/10 border border-primary/20 rounded-xl mb-6">
                                            <p className="text-xs font-medium text-primary-foreground text-center leading-relaxed">
                                                Your account has Two-Factor Authentication enabled.
                                                Please enter your cloud password to continue.
                                            </p>
                                        </div>
                                        <label className="block text-[11px] font-bold text-slate uppercase tracking-widest ml-1">Cloud Password</label>
                                        <div className="relative group/input">
                                            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate transition-colors group-focus-within/input:text-primary" />
                                            <input
                                                type="password"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                placeholder="Enter your password"
                                                className="w-full h-14 bg-white/5 border border-white/10 text-white placeholder:text-white/20 focus:bg-white/10 focus:border-primary/50 transition-all text-lg rounded-xl pl-12 pr-4 outline-none shadow-inner"
                                                autoFocus
                                            />
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-4">
                                        <button
                                            type="submit"
                                            disabled={loading || !password}
                                            className="w-full h-12 bg-gradient-to-r from-primary to-blue-500 hover:from-primary-pressed hover:to-blue-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-[0_0_20px_rgba(124,92,255,0.3)] hover:shadow-[0_0_25px_rgba(124,92,255,0.5)] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {loading ? "Verifying..." : "Unlock"}
                                        </button>
                                        <button type="button" onClick={() => { setStep("code"); setPassword(""); setError(null); }} className="text-xs font-medium text-white/40 hover:text-white/80 transition-colors py-2">
                                            Back to Code Entry
                                        </button>
                                    </div>
                                </motion.form>
                            )}
                        </div>
                    )}
                </AnimatePresence>

                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-6 relative z-10"
                    >
                        <Alert variant="destructive" className="border-red-500/30 bg-red-500/10 text-red-200">
                            <AlertCircle className="w-4 h-4" />
                            <AlertDescription className="font-medium text-xs">{error}</AlertDescription>
                        </Alert>
                    </motion.div>
                )}
                </motion.div>
            </div>


            <Dialog open={showHelp} onOpenChange={setShowHelp}>
                <DialogContent className="max-w-md gap-0 overflow-hidden p-0 bg-surface/95 backdrop-blur-xl border-white/10 shadow-2xl">
                    <DialogHeader className="border-b border-white/5 px-6 py-5">
                        <DialogTitle className="text-xl font-bold">Getting started</DialogTitle>
                        <DialogDescription className="text-white/50 text-sm mt-1">
                            You only need a Telegram API ID and API Hash.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 px-6 py-6 bg-black/20">
                        <Alert className="border-primary/20 bg-primary/10">
                            <ShieldCheck className="h-4 w-4 text-primary" />
                            <AlertDescription className="text-white/70 text-sm">
                                Credentials stay on this device and are used only to connect your Telegram account.
                            </AlertDescription>
                        </Alert>

                        <HelpStep number="1" title="Open the developer portal">
                            Sign in at <button type="button" onClick={() => open('https://my.telegram.org')} className="text-primary hover:text-primary-pressed font-medium transition-colors">my.telegram.org</button>.
                        </HelpStep>

                        <HelpStep number="2" title="Create an app">
                            Choose <span className="font-medium text-white">API development tools</span>, then create any app name.
                        </HelpStep>

                        <HelpStep number="3" title="Paste both values">
                            Copy the <span className="font-medium text-white">API ID</span> and <span className="font-medium text-white">API Hash</span> into Telegrab.
                        </HelpStep>
                    </div>

                    <DialogFooter className="border-t border-white/5 px-6 py-4 bg-surface">
                        <DialogClose asChild>
                            <Button type="button" variant="ghost" className="hover:bg-white/5">
                                Done
                            </Button>
                        </DialogClose>
                        <Button
                            type="button"
                            onClick={() => open('https://my.telegram.org')}
                            className="bg-primary hover:bg-primary-pressed text-white shadow-lg"
                        >
                            Open portal
                            <ExternalLink className="h-4 w-4 ml-2" />
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Grid pattern overlay */}
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCI+PHBhdGggZD0iTTAgMGg0MHY0MEgwem0zOSAzOXYtMzhIMXYzOHoiIGZpbGw9IiNmZmZmZmYwMyIvPjwvc3ZnPg==')] opacity-30 pointer-events-none mix-blend-overlay" />
            
            {/* Soft glows */}
            <div className="fixed top-[-20%] left-[-10%] w-[600px] h-[600px] bg-primary/20 rounded-full blur-[140px] pointer-events-none -z-10" />
            <div className="fixed bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-blue-600/15 rounded-full blur-[120px] pointer-events-none -z-10" />
            <div className="fixed top-[40%] left-[40%] w-[300px] h-[300px] bg-purple-500/10 rounded-full blur-[100px] pointer-events-none -z-10" />
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
        <Card className="bg-white/5 border-white/10 shadow-none">
            <CardContent className="flex gap-4 p-4">
                <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-bold text-white shadow-inner">
                    {number}
                </span>
                <div className="min-w-0 pt-0.5">
                    <h3 className="text-sm font-bold text-white mb-1">{title}</h3>
                    <p className="text-sm leading-relaxed text-white/50">{children}</p>
                </div>
            </CardContent>
        </Card>
    );
}
