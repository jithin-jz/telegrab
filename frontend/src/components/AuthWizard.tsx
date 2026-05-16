import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { motion, AnimatePresence } from "framer-motion";
import { 
    Phone, 
    Key, 
    Lock, 
    ArrowRight, 
    ShieldCheck, 
    HelpCircle, 
    ExternalLink, 
    QrCode, 
    AlertCircle, 
    Cloud, 
    Zap, 
    Shield,
    LockIcon,
    Smartphone
} from "lucide-react";
import { load } from '@tauri-apps/plugin-store';
import { open } from '@tauri-apps/plugin-shell';
import { QRCodeSVG } from 'qrcode.react';

import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Alert, AlertDescription } from "./ui/alert";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./ui/card";
import {
    Dialog,
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
                <div className="w-20 h-20 bg-destructive/10 rounded-full flex items-center justify-center mb-6">
                    <ShieldCheck className="w-10 h-10 text-error" />
                </div>
                <h1 className="text-2xl font-bold text-foreground mb-4">Desktop App Required</h1>
                <p className="text-muted-foreground mb-6 leading-relaxed">
                    You are viewing the internal development server in a browser.
                    This application cannot function here because it requires access to the system backend (Rust).
                </p>
                <div className="p-4 bg-surface-soft rounded-xl border border-hairline text-sm text-foreground font-medium">
                    Please open the <strong className="text-primary">Telegrab</strong> window in your OS taskbar/dock to continue.
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
            setError("API ID and API Hash cannot contain spaces.");
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
        <div className="flex-1 w-full auth-gradient flex items-center justify-center p-4 relative overflow-hidden">
            {/* Minimal Background Decor */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,var(--color-primary),transparent_50%)] opacity-[0.03] pointer-events-none" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,var(--color-link-blue),transparent_50%)] opacity-[0.03] pointer-events-none" />
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCI+PHBhdGggZD0iTTAgMGg0MHY0MEgwem0zOSAzOXYtMzhIMXYzOHoiIGZpbGw9IiNmZmZmZmYwMiIvPjwvc3ZnPg==')] opacity-20 pointer-events-none" />

            <div className="flex flex-col md:flex-row items-center justify-center gap-12 lg:gap-24 w-full max-w-5xl z-10">
                
                {/* ── LEFT: Branding ── */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    className="flex-1 max-w-md space-y-8 hidden md:block"
                >
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
                            <img src={logoUrl} alt="Telegrab" className="w-6 h-6 filter brightness-0 invert" />
                        </div>
                        <span className="text-2xl font-bold tracking-tight text-foreground">Telegrab</span>
                    </div>

                    <div className="space-y-4">
                        <h1 className="text-4xl lg:text-5xl font-bold tracking-tight leading-[1.1]">
                            Your files, <br/>
                            <span className="text-primary">your cloud.</span>
                        </h1>
                        <p className="text-lg text-slate font-medium leading-relaxed">
                            A minimal, professional interface for your personal Telegram-powered storage. Unlimited, private, and fast.
                        </p>
                    </div>

                    <div className="grid gap-6">
                        {[
                            { icon: Cloud, title: "Infinite Space", desc: "Leverage Telegram's unlimited cloud.", color: "text-blue-400" },
                            { icon: Shield, title: "End-to-End Privacy", desc: "Encryption by default on your device.", color: "text-purple-400" },
                            { icon: Zap, title: "High Performance", desc: "Multi-part parallel processing.", color: "text-orange-400" }
                        ].map((item, i) => (
                            <motion.div 
                                key={i}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: 0.3 + i * 0.1 }}
                                className="flex items-start gap-4"
                            >
                                <div className={`mt-1 ${item.color}`}>
                                    <item.icon className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-foreground">{item.title}</h3>
                                    <p className="text-sm text-slate font-medium">{item.desc}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>

                {/* ── RIGHT: Auth Card ── */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.4 }}
                    className="w-full max-w-[420px]"
                >
                    <Card className="border-hairline/50 bg-surface/50 backdrop-blur-sm shadow-xl">
                        <CardHeader className="space-y-1 text-center">
                            <div className="md:hidden flex justify-center mb-4">
                                <img src={logoUrl} alt="Telegrab" className="w-10 h-10" />
                            </div>
                            <CardTitle className="text-2xl font-bold tracking-tight">Get Started</CardTitle>
                            <CardDescription className="text-sm font-medium">
                                Connect your Telegram API to continue
                            </CardDescription>
                        </CardHeader>

                        <CardContent className="space-y-6 pt-4">
                            <AnimatePresence mode="wait">
                                {floodWait ? (
                                    <motion.div
                                        key="flood"
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="py-6 text-center space-y-6"
                                    >
                                        <div className="w-16 h-16 bg-error/10 rounded-full flex items-center justify-center mx-auto text-error">
                                            <AlertCircle className="w-8 h-8" />
                                        </div>
                                        <div className="space-y-2">
                                            <h2 className="text-lg font-bold">Too Many Requests</h2>
                                            <p className="text-sm text-slate font-medium">Telegram has limited your actions. Please wait.</p>
                                        </div>
                                        <div className="text-4xl font-mono text-primary font-bold">
                                            {Math.floor(floodWait / 60)}:{(floodWait % 60).toString().padStart(2, '0')}
                                        </div>
                                        <p className="text-[11px] text-destructive font-medium uppercase tracking-wider">
                                            Do not restart the app
                                        </p>
                                    </motion.div>
                                ) : (
                                    <div className="space-y-4">
                                        {step === "setup" && (
                                            <motion.form
                                                key="setup"
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                onSubmit={handleSetupSubmit}
                                                className="space-y-4"
                                            >
                                                <div className="space-y-2">
                                                    <Label htmlFor="api-id" className="text-xs font-semibold text-slate uppercase tracking-wider">API ID</Label>
                                                    <div className="relative">
                                                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate/50" />
                                                        <Input
                                                            id="api-id"
                                                            placeholder="12345678"
                                                            value={apiId}
                                                            onChange={(e) => setApiId(e.target.value)}
                                                            className="pl-10 h-11 bg-canvas/50 font-mono text-sm tracking-widest"
                                                            autoComplete="off"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="space-y-2">
                                                    <Label htmlFor="api-hash" className="text-xs font-semibold text-slate uppercase tracking-wider">API Hash</Label>
                                                    <div className="relative">
                                                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate/50" />
                                                        <Input
                                                            id="api-hash"
                                                            placeholder="abcdef123456…"
                                                            value={apiHash}
                                                            onChange={(e) => setApiHash(e.target.value)}
                                                            className="pl-10 h-11 bg-canvas/50 font-mono text-sm tracking-widest"
                                                            autoComplete="off"
                                                        />
                                                    </div>
                                                </div>
                                                <Button type="submit" className="w-full h-11 text-sm font-bold shadow-sm" size="lg">
                                                    Configure <ArrowRight className="w-4 h-4 ml-2" />
                                                </Button>
                                            </motion.form>
                                        )}

                                        {step === "phone" && (
                                            <motion.div
                                                key="phone"
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                className="space-y-6"
                                            >
                                                <div className="flex p-1 bg-surface-soft rounded-lg border border-hairline/50">
                                                    <button
                                                        type="button"
                                                        onClick={() => { setLoginMethod('phone'); setQrUrl(null); setQrPolling(false); setError(null); }}
                                                        className={`flex-1 py-1.5 text-xs font-bold rounded-md flex items-center justify-center gap-2 transition-all ${
                                                            loginMethod === 'phone' ? 'bg-surface text-foreground shadow-sm' : 'text-slate hover:text-foreground'
                                                        }`}
                                                    >
                                                        <Smartphone className="w-3.5 h-3.5" /> Phone
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => { setLoginMethod('qr'); setError(null); handleQrLogin(); }}
                                                        className={`flex-1 py-1.5 text-xs font-bold rounded-md flex items-center justify-center gap-2 transition-all ${
                                                            loginMethod === 'qr' ? 'bg-surface text-foreground shadow-sm' : 'text-slate hover:text-foreground'
                                                        }`}
                                                    >
                                                        <QrCode className="w-3.5 h-3.5" /> QR Code
                                                    </button>
                                                </div>

                                                {loginMethod === 'phone' ? (
                                                    <form onSubmit={handlePhoneSubmit} className="space-y-4">
                                                        <div className="space-y-2">
                                                            <Label className="text-xs font-semibold text-slate uppercase tracking-wider">Phone Number</Label>
                                                            <div className="relative">
                                                                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate/50" />
                                                                <Input
                                                                    type="tel"
                                                                    placeholder="+1 234 567 8900"
                                                                    value={phone}
                                                                    onChange={(e) => setPhone(e.target.value)}
                                                                    className="pl-10 h-11 bg-canvas/50 font-medium text-base tracking-wide"
                                                                />
                                                            </div>
                                                        </div>
                                                        <Button type="submit" disabled={loading} className="w-full h-11 font-bold" size="lg">
                                                            {loading ? "Connecting..." : "Continue"}
                                                        </Button>
                                                    </form>
                                                ) : (
                                                    <div className="flex flex-col items-center gap-4 py-2">
                                                        {!qrUrl && loading ? (
                                                            <div className="w-48 h-48 rounded-xl bg-surface-soft animate-pulse flex items-center justify-center">
                                                                <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                                            </div>
                                                        ) : qrUrl ? (
                                                            <div className="space-y-4 flex flex-col items-center">
                                                                <div className="p-3 bg-white rounded-xl shadow-lg">
                                                                    <QRCodeSVG value={qrUrl} size={160} level="M" />
                                                                </div>
                                                                <div className="text-center space-y-1 px-4">
                                                                    <p className="text-sm font-bold text-foreground">Scan with Telegram</p>
                                                                    <p className="text-xs text-slate font-medium leading-relaxed">
                                                                        Settings &gt; Devices &gt; Link Desktop
                                                                    </p>
                                                                </div>
                                                                {qrPolling && (
                                                                    <div className="flex items-center gap-2 text-[11px] font-bold text-primary bg-primary/5 px-3 py-1.5 rounded-full border border-primary/10">
                                                                        <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                                                        Waiting for scan...
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ) : null}
                                                    </div>
                                                )}
                                                <Button variant="ghost" size="sm" onClick={() => setStep("setup")} className="w-full text-xs font-semibold text-slate hover:text-foreground">
                                                    Back to Configuration
                                                </Button>
                                            </motion.div>
                                        )}

                                        {step === "code" && (
                                            <motion.form
                                                key="code"
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                onSubmit={handleCodeSubmit}
                                                className="space-y-4"
                                            >
                                                <div className="space-y-2">
                                                    <Label className="text-xs font-semibold text-slate uppercase tracking-wider text-center block">Verification Code</Label>
                                                    <Input
                                                        type="text"
                                                        value={code}
                                                        onChange={(e) => setCode(e.target.value)}
                                                        placeholder="12345"
                                                        className="h-14 text-2xl font-mono tracking-[0.5em] text-center bg-canvas/50"
                                                        autoFocus
                                                    />
                                                </div>
                                                <Button type="submit" disabled={loading} className="w-full h-11 font-bold">
                                                    {loading ? "Verifying..." : "Sign In"}
                                                </Button>
                                                <Button variant="ghost" size="sm" onClick={() => setStep("phone")} className="w-full text-xs font-semibold text-slate">
                                                    Change Phone Number
                                                </Button>
                                            </motion.form>
                                        )}

                                        {step === "password" && (
                                            <motion.form
                                                key="password"
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                onSubmit={handlePasswordSubmit}
                                                className="space-y-4"
                                            >
                                                <Alert className="bg-primary/5 border-primary/10 py-3">
                                                    <LockIcon className="w-3.5 h-3.5 text-primary" />
                                                    <AlertDescription className="text-xs font-medium text-foreground">
                                                        2FA Enabled. Enter cloud password.
                                                    </AlertDescription>
                                                </Alert>
                                                <div className="space-y-2">
                                                    <Label className="text-xs font-semibold text-slate uppercase tracking-wider">Cloud Password</Label>
                                                    <div className="relative">
                                                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate/50" />
                                                        <Input
                                                            type="password"
                                                            value={password}
                                                            onChange={(e) => setPassword(e.target.value)}
                                                            className="pl-10 h-11 bg-canvas/50"
                                                            autoFocus
                                                        />
                                                    </div>
                                                </div>
                                                <Button type="submit" disabled={loading || !password} className="w-full h-11 font-bold">
                                                    {loading ? "Unlocking..." : "Unlock Vault"}
                                                </Button>
                                                <Button variant="ghost" size="sm" onClick={() => { setStep("code"); setPassword(""); setError(null); }} className="w-full text-xs font-semibold text-slate">
                                                    Back to Code
                                                </Button>
                                            </motion.form>
                                        )}
                                    </div>
                                )}
                            </AnimatePresence>

                            {error && (
                                <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }}>
                                    <Alert variant="destructive" className="py-2.5">
                                        <AlertCircle className="w-3.5 h-3.5" />
                                        <AlertDescription className="text-xs font-semibold leading-tight">{error}</AlertDescription>
                                    </Alert>
                                </motion.div>
                            )}
                        </CardContent>

                        <CardFooter className="flex flex-col gap-3 pb-8">
                            {step === "setup" && (
                                <button
                                    type="button"
                                    onClick={() => setShowHelp(true)}
                                    className="text-xs font-semibold text-slate hover:text-primary transition-colors flex items-center gap-1.5"
                                >
                                    <HelpCircle className="w-3.5 h-3.5" />
                                    Getting API credentials
                                </button>
                            )}

                            {import.meta.env.DEV && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => onLogin()}
                                    className="w-full text-[10px] uppercase tracking-widest font-bold h-8 border-dashed opacity-40 hover:opacity-100"
                                >
                                    Bypass (Dev)
                                </Button>
                            )}
                        </CardFooter>
                    </Card>
                </motion.div>
            </div>

            {/* Help Dialog */}
            <Dialog open={showHelp} onOpenChange={setShowHelp}>
                <DialogContent className="max-w-md bg-surface/95 backdrop-blur-xl border-hairline/50">
                    <DialogHeader>
                        <DialogTitle className="text-xl font-bold tracking-tight">Configuration Guide</DialogTitle>
                        <DialogDescription className="font-medium">
                            Create your Telegram application to get API credentials.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="grid gap-4 py-4">
                        {[
                            { step: "1", title: "Open Portal", desc: "Sign in at my.telegram.org", link: "https://my.telegram.org" },
                            { step: "2", title: "API tools", desc: "Select 'API development tools'", link: null },
                            { step: "3", title: "Create App", desc: "Provide any name and platform", link: null }
                        ].map((item, i) => (
                            <div key={i} className="flex gap-4 p-3 rounded-lg bg-muted/30 border border-border/20">
                                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0">
                                    {item.step}
                                </div>
                                <div className="space-y-0.5">
                                    <h4 className="text-sm font-bold">{item.title}</h4>
                                    <p className="text-xs text-slate font-medium">{item.desc}</p>
                                    {item.link && (
                                        <button onClick={() => open(item.link!)} className="text-[10px] text-primary font-bold uppercase tracking-wider flex items-center gap-1 mt-1 hover:underline">
                                            Open <ExternalLink className="w-2.5 h-2.5" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                        
                        <div className="flex items-center gap-2 p-3 bg-primary/5 rounded-lg border border-primary/10 mt-2">
                            <ShieldCheck className="w-4 h-4 text-primary shrink-0" />
                            <p className="text-[11px] font-medium text-slate leading-snug">
                                Your API credentials are stored securely on this machine and never shared.
                            </p>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="secondary" onClick={() => setShowHelp(false)} className="font-bold">
                            Got it
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
