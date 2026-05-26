import { useState, useEffect, useRef } from 'react';
import { invoke } from '../lib/platform/core';
import { motion, AnimatePresence } from 'framer-motion';
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
  Smartphone,
} from 'lucide-react';
import { load } from '../lib/platform/store';
import { open } from '../lib/platform/shell';
import { QRCodeSVG } from 'qrcode.react';

import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Alert, AlertDescription } from './ui/alert';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import logoUrl from '../assets/logo.svg';

type Step = 'setup' | 'phone' | 'code' | 'password';

export function AuthWizard({ onLogin }: { onLogin: () => void }) {
  const isBrowser =
    typeof window !== 'undefined' &&
    window.location.protocol !== 'file:' &&
    !window.location.search.includes('platform=desktop') &&
    !('pywebview' in window);

  if (isBrowser) {
    return (
      <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center p-8 text-center">
        <div className="bg-destructive/10 mb-6 flex h-20 w-20 items-center justify-center rounded-full">
          <ShieldCheck className="text-error h-10 w-10" />
        </div>
        <h1 className="text-foreground mb-4 text-2xl font-bold">Desktop App Required</h1>
        <p className="text-muted-foreground mb-6 leading-relaxed">
          You are viewing the internal development server in a browser. This application cannot
          function here because it requires access to the system backend (Python).
        </p>
        <div className="bg-surface-soft border-hairline text-foreground rounded-xl border p-4 text-sm font-medium">
          Please open the <strong className="text-primary">Telegrab</strong> window in your OS
          taskbar/dock to continue.
        </div>
      </div>
    );
  }

  const [step, setStep] = useState<Step>('setup');
  const [loading, setLoading] = useState(false);

  const [apiId, setApiId] = useState('');
  const [apiHash, setApiHash] = useState('');

  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
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
      setFloodWait((prev) => {
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
      setError('API ID and API Hash cannot contain spaces.');
      return;
    }

    if (!apiId || !apiHash) {
      setError('Both API ID and Hash are required.');
      return;
    }
    setError(null);
    await saveCredentials();
    setStep('phone');
    setLoginMethod('phone');
    setQrUrl(null);
    setQrPolling(false);
  };

  const handleQrLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const idInt = parseInt(apiId, 10);
      if (isNaN(idInt)) throw new Error('API ID must be a number');

      const url = await invoke<string>('cmd_auth_qr_login', {
        apiId: idInt,
        apiHash: apiHash,
      });

      if (url === '__authorized__') {
        onLogin();
        return;
      }
      if (url === '__password_required__') {
        setLoginMethod('phone');
        setStep('password');
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
        const res = await invoke<{ success: boolean; next_step?: string }>('cmd_auth_qr_poll');
        console.log('[Auth] QR Poll Result:', res);
        
        if (res.success) {
          setQrPolling(false);
          if (res.next_step === 'password') {
            setStep('password');
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
      if (isNaN(idInt)) throw new Error('API ID must be a number');

      await invoke('cmd_auth_request_code', {
        phone,
        apiId: idInt,
        apiHash: apiHash,
      });
      setStep('code');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : JSON.stringify(err);
      if (msg.includes('FLOOD_WAIT_')) {
        const parts = msg.split('FLOOD_WAIT_');
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
      const res = await invoke<{ success: boolean; next_step?: string }>('cmd_auth_sign_in', {
        code,
      });
      if (res.success) {
        onLogin();
      } else if (res.next_step === 'password') {
        setStep('password');
      } else {
        setError('Unknown error');
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
      const res = await invoke<{ success: boolean; next_step?: string }>(
        'cmd_auth_check_password',
        { password }
      );
      if (res.success) {
        onLogin();
      } else {
        setError('Password verification failed.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-gradient relative flex w-full flex-1 items-center justify-center overflow-hidden p-4">
      {/* Minimal Background Decor */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,var(--color-primary),transparent_50%)] opacity-[0.03]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,var(--color-link-blue),transparent_50%)] opacity-[0.03]" />
      <div className="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCI+PHBhdGggZD0iTTAgMGg0MHY0MEgwem0zOSAzOXYtMzhIMXYzOHoiIGZpbGw9IiNmZmZmZmYwMiIvPjwvc3ZnPg==')] opacity-20" />

      <div className="z-10 flex w-full max-w-5xl flex-col items-center justify-center gap-12 md:flex-row lg:gap-24">
        {/* ── LEFT: Branding ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="hidden max-w-md flex-1 space-y-8 md:block"
        >
          <div className="flex items-center gap-4">
            <div className="auth-glass border-white/10 shadow-primary/20 flex h-12 w-12 items-center justify-center rounded-2xl shadow-xl relative overflow-hidden group">
              <img src="/logo.svg" alt="Telegrab" className="w-7 h-7 relative z-10" />
              <motion.div 
                className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/20 to-transparent -translate-x-full"
                animate={{ translateX: ['100%', '-100%'] }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              />
            </div>
            <span className="text-foreground text-3xl font-bold tracking-tight">Telegrab</span>
          </div>

          <div className="space-y-5">
            <h1 className="text-foreground text-5xl leading-[1.05] font-bold tracking-tight lg:text-6xl">
              Your files, <br />
              <span className="text-primary">reimagined.</span>
            </h1>
          </div>

          <div className="grid gap-6">
            {[
              {
                icon: Cloud,
                title: 'Unlimited Storage',
                desc: "No caps, no limits powered by Telegram.",
                color: 'text-primary',
              },
              {
                icon: Shield,
                title: 'Private & Secure',
                desc: 'Your files stay between you and Telegram.',
                color: 'text-emerald-500',
              },
              {
                icon: Zap,
                title: 'Lightning Fast',
                desc: 'Stream 4K, parallel uploads, instant access.',
                color: 'text-amber-500',
              },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.1 }}
                className="flex items-start gap-4"
              >
                <div className={`mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-current/10 ${item.color}`}>
                  <item.icon className="h-4.5 w-4.5" strokeWidth={2} />
                </div>
                <div>
                  <h3 className="text-foreground font-semibold">{item.title}</h3>
                  <p className="text-slate text-sm font-medium">{item.desc}</p>
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
          <Card className="border-hairline/50 bg-surface/50 shadow-xl backdrop-blur-sm">
            <CardHeader className="space-y-1 text-center">
              <div className="mb-4 flex justify-center md:hidden">
                <img src={logoUrl} alt="Telegrab" className="h-10 w-10" />
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
                    className="space-y-6 py-6 text-center"
                  >
                    <div className="bg-error/10 text-error mx-auto flex h-16 w-16 items-center justify-center rounded-full">
                      <AlertCircle className="h-8 w-8" />
                    </div>
                    <div className="space-y-2">
                      <h2 className="text-lg font-bold">Too Many Requests</h2>
                      <p className="text-slate text-sm font-medium">
                        Telegram has limited your actions. Please wait.
                      </p>
                    </div>
                    <div className="text-primary font-mono text-4xl font-bold">
                      {Math.floor(floodWait / 60)}:{(floodWait % 60).toString().padStart(2, '0')}
                    </div>
                    <p className="text-destructive text-[11px] font-medium tracking-wider uppercase">
                      Do not restart the app
                    </p>
                  </motion.div>
                ) : (
                  <div className="space-y-4">
                    {step === 'setup' && (
                      <motion.form
                        key="setup"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        onSubmit={handleSetupSubmit}
                        className="space-y-4"
                      >
                        <div className="space-y-2">
                          <Label
                            htmlFor="api-id"
                            className="text-slate text-xs font-semibold tracking-wider uppercase"
                          >
                            API ID
                          </Label>
                          <div className="relative">
                            <Key className="text-slate/50 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                            <Input
                              id="api-id"
                              placeholder="12345678"
                              value={apiId}
                              onChange={(e) => setApiId(e.target.value)}
                              className="bg-canvas/50 h-11 pl-10 font-mono text-sm tracking-widest"
                              autoComplete="off"
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label
                            htmlFor="api-hash"
                            className="text-slate text-xs font-semibold tracking-wider uppercase"
                          >
                            API Hash
                          </Label>
                          <div className="relative">
                            <Lock className="text-slate/50 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                            <Input
                              id="api-hash"
                              placeholder="abcdef123456…"
                              value={apiHash}
                              onChange={(e) => setApiHash(e.target.value)}
                              className="bg-canvas/50 h-11 pl-10 font-mono text-sm tracking-widest"
                              autoComplete="off"
                            />
                          </div>
                        </div>
                        <Button
                          type="submit"
                          className="h-11 w-full text-sm font-bold shadow-sm"
                          size="lg"
                        >
                          Configure <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                      </motion.form>
                    )}

                    {step === 'phone' && (
                      <motion.div
                        key="phone"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="space-y-6"
                      >
                        <div className="bg-surface-soft border-hairline/50 flex rounded-lg border p-1">
                          <button
                            type="button"
                            onClick={() => {
                              setLoginMethod('phone');
                              setQrUrl(null);
                              setQrPolling(false);
                              setError(null);
                            }}
                            className={`flex flex-1 items-center justify-center gap-2 rounded-md py-1.5 text-xs font-bold transition-all ${
                              loginMethod === 'phone'
                                ? 'bg-surface text-foreground shadow-sm'
                                : 'text-slate hover:text-foreground'
                            }`}
                          >
                            <Smartphone className="h-3.5 w-3.5" /> Phone
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setLoginMethod('qr');
                              setError(null);
                              handleQrLogin();
                            }}
                            className={`flex flex-1 items-center justify-center gap-2 rounded-md py-1.5 text-xs font-bold transition-all ${
                              loginMethod === 'qr'
                                ? 'bg-surface text-foreground shadow-sm'
                                : 'text-slate hover:text-foreground'
                            }`}
                          >
                            <QrCode className="h-3.5 w-3.5" /> QR Code
                          </button>
                        </div>

                        {loginMethod === 'phone' ? (
                          <form onSubmit={handlePhoneSubmit} className="space-y-4">
                            <div className="space-y-2">
                              <Label className="text-slate text-xs font-semibold tracking-wider uppercase">
                                Phone Number
                              </Label>
                              <div className="relative">
                                <Phone className="text-slate/50 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                                <Input
                                  type="tel"
                                  placeholder="+1 234 567 8900"
                                  value={phone}
                                  onChange={(e) => setPhone(e.target.value)}
                                  className="bg-canvas/50 h-11 pl-10 text-base font-medium tracking-wide"
                                />
                              </div>
                            </div>
                            <Button
                              type="submit"
                              disabled={loading}
                              className="h-11 w-full font-bold"
                              size="lg"
                            >
                              {loading ? 'Connecting...' : 'Continue'}
                            </Button>
                          </form>
                        ) : (
                          <div className="flex flex-col items-center gap-4 py-2">
                            {!qrUrl && loading ? (
                              <div className="bg-surface-soft flex h-48 w-48 animate-pulse items-center justify-center rounded-xl">
                                <div className="border-primary h-6 w-6 animate-spin rounded-full border-2 border-t-transparent" />
                              </div>
                            ) : qrUrl ? (
                              <div className="flex flex-col items-center space-y-4">
                                <div className="rounded-xl bg-white p-3 shadow-lg">
                                  <QRCodeSVG value={qrUrl} size={160} level="M" />
                                </div>
                                <div className="space-y-1 px-4 text-center">
                                  <p className="text-foreground text-sm font-bold">
                                    Scan with Telegram
                                  </p>
                                  <p className="text-slate text-xs leading-relaxed font-medium">
                                    Settings &gt; Devices &gt; Link Desktop
                                  </p>
                                </div>
                                {qrPolling && (
                                  <div className="text-primary bg-primary/5 border-primary/10 flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold">
                                    <div className="border-primary h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" />
                                    Waiting for scan...
                                  </div>
                                )}
                              </div>
                            ) : null}
                          </div>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setStep('setup')}
                          className="text-slate hover:text-foreground w-full text-xs font-semibold"
                        >
                          Back to Configuration
                        </Button>
                      </motion.div>
                    )}

                    {step === 'code' && (
                      <motion.form
                        key="code"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        onSubmit={handleCodeSubmit}
                        className="space-y-4"
                      >
                        <div className="space-y-2">
                          <Label className="text-slate block text-center text-xs font-semibold tracking-wider uppercase">
                            Verification Code
                          </Label>
                          <Input
                            type="text"
                            value={code}
                            onChange={(e) => setCode(e.target.value)}
                            placeholder="12345"
                            className="bg-canvas/50 h-14 text-center font-mono text-2xl tracking-[0.5em]"
                            autoFocus
                          />
                        </div>
                        <Button type="submit" disabled={loading} className="h-11 w-full font-bold">
                          {loading ? 'Verifying...' : 'Sign In'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setStep('phone')}
                          className="text-slate w-full text-xs font-semibold"
                        >
                          Change Phone Number
                        </Button>
                      </motion.form>
                    )}

                    {step === 'password' && (
                      <motion.form
                        key="password"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        onSubmit={handlePasswordSubmit}
                        className="space-y-4"
                      >
                        <Alert className="bg-primary/5 border-primary/10 py-3">
                          <LockIcon className="text-primary h-3.5 w-3.5" />
                          <AlertDescription className="text-foreground text-xs font-medium">
                            2FA Enabled. Enter cloud password.
                          </AlertDescription>
                        </Alert>
                        <div className="space-y-2">
                          <Label className="text-slate text-xs font-semibold tracking-wider uppercase">
                            Cloud Password
                          </Label>
                          <div className="relative">
                            <Lock className="text-slate/50 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                            <Input
                              type="password"
                              value={password}
                              onChange={(e) => setPassword(e.target.value)}
                              className="bg-canvas/50 h-11 pl-10"
                              autoFocus
                            />
                          </div>
                        </div>
                        <Button
                          type="submit"
                          disabled={loading || !password}
                          className="h-11 w-full font-bold"
                        >
                          {loading ? 'Unlocking...' : 'Unlock Vault'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setStep('code');
                            setPassword('');
                            setError(null);
                          }}
                          className="text-slate w-full text-xs font-semibold"
                        >
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
                    <AlertCircle className="h-3.5 w-3.5" />
                    <AlertDescription className="text-xs leading-tight font-semibold">
                      {error}
                    </AlertDescription>
                  </Alert>
                </motion.div>
              )}
            </CardContent>

            <CardFooter className="flex flex-col gap-3 pb-8">
              {step === 'setup' && (
                <button
                  type="button"
                  onClick={() => setShowHelp(true)}
                  className="text-slate hover:text-primary flex items-center gap-1.5 text-xs font-semibold transition-colors"
                >
                  <HelpCircle className="h-3.5 w-3.5" />
                  Getting API credentials
                </button>
              )}

              {import.meta.env.DEV && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onLogin()}
                  className="h-8 w-full border-dashed text-[10px] font-bold tracking-widest uppercase opacity-40 hover:opacity-100"
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
        <DialogContent className="bg-surface/95 border-hairline/50 max-w-md backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold tracking-tight">
              Configuration Guide
            </DialogTitle>
            <DialogDescription className="font-medium">
              Create your Telegram application to get API credentials.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {[
              {
                step: '1',
                title: 'Open Portal',
                desc: 'Sign in at my.telegram.org',
                link: 'https://my.telegram.org',
              },
              { step: '2', title: 'API tools', desc: "Select 'API development tools'", link: null },
              { step: '3', title: 'Create App', desc: 'Provide any name and platform', link: null },
            ].map((item, i) => (
              <div
                key={i}
                className="bg-muted/30 border-border/20 flex gap-4 rounded-lg border p-3"
              >
                <div className="bg-primary/10 text-primary flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold">
                  {item.step}
                </div>
                <div className="space-y-0.5">
                  <h4 className="text-sm font-bold">{item.title}</h4>
                  <p className="text-slate text-xs font-medium">{item.desc}</p>
                  {item.link && (
                    <button
                      onClick={() => open(item.link!)}
                      className="text-primary mt-1 flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase hover:underline"
                    >
                      Open <ExternalLink className="h-2.5 w-2.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}

            <div className="bg-primary/5 border-primary/10 mt-2 flex items-center gap-2 rounded-lg border p-3">
              <ShieldCheck className="text-primary h-4 w-4 shrink-0" />
              <p className="text-slate text-[11px] leading-snug font-medium">
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
