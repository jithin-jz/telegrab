import { useState, useEffect, useRef, lazy, Suspense } from 'react';
import { invoke } from './lib/platform/core';
import { load } from './lib/platform/store';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from './components/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { OfflineBanner } from './components/OfflineBanner';
import { SkipNav } from './components/ui/skip-nav';
import { StatusAnnouncer } from './components/ui/status-announcer';
import { motion, AnimatePresence } from 'framer-motion';
import './styles/globals.css';

import { Toaster } from 'sonner';
import { ConfirmProvider } from './contexts/ConfirmContext';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';
import { UpdateProvider } from './contexts/UpdateContext';
import { useNetworkStatus } from './hooks/useNetworkStatus';
import { TooltipProvider } from './components/ui/tooltip';

const AuthWizard = lazy(() => import('./components/AuthWizard').then(m => ({ default: m.AuthWizard })));

const queryClient = new QueryClient();

const TOAST_STYLE = {
  background: 'var(--color-surface)',
  backdropFilter: 'blur(12px)',
  border: '1px solid var(--color-hairline)',
  color: 'var(--color-ink)',
} as const;

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

const TelegramLogo = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" className={className}>
    <rect width="512" height="512" rx="96" fill="#f43f5e"/>
    <text x="256" y="370" fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="240" fill="#ffffff" textAnchor="middle">tb</text>
  </svg>
);

function AppContent() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading');
  const { settings, isLoaded: settingsLoaded } = useSettings();
  const isOnline = useNetworkStatus();

  // Minimise the window on launch if the user has Start Minimised enabled.
  // Runs once per app session, as soon as the persisted setting is loaded.
  const startMinimisedHandled = useRef(false);
  useEffect(() => {
    if (!settingsLoaded) return;
    if (startMinimisedHandled.current) return;
    startMinimisedHandled.current = true;
    if (settings.startMinimised) {
      invoke('cmd_window_minimize').catch(() => {
        // best-effort; non-fatal if the host doesn't support it
      });
    }
  }, [settingsLoaded, settings.startMinimised]);

  useEffect(() => {
    const checkSession = async () => {
      try {
        const store = await load('config.json');
        const savedId = await store.get<string>('api_id');
        const savedHash = await store.get<string>('api_hash');

        if (!savedId || !savedHash) {
          setAuthStatus('unauthenticated');
          return;
        }

        const apiId = parseInt(savedId, 10);
        if (isNaN(apiId)) {
          setAuthStatus('unauthenticated');
          return;
        }

        await invoke('cmd_connect', { apiId, apiHash: savedHash });
        const ok = await invoke<boolean>('cmd_check_connection');
        
        // Give the splash screen a tiny bit of extra time to look good
        setTimeout(() => {
          setAuthStatus(ok ? 'authenticated' : 'unauthenticated');
        }, 350);
      } catch (err) {
        console.warn('Session restore failed, showing login:', err);
        setAuthStatus('unauthenticated');
      }
    };

    checkSession();
  }, []);

  return (
    <>
      <SkipNav />
      <StatusAnnouncer />
      <main 
        className="text-foreground selection:bg-primary/30 relative flex h-screen w-screen flex-col overflow-hidden bg-canvas"
      >
        <OfflineBanner isOffline={!isOnline} />
      <div className="flex-1 flex flex-col min-h-0">
        <Toaster
          theme="dark"
          position="bottom-center"
          toastOptions={{ style: TOAST_STYLE }}
        />
        
        <AnimatePresence mode="wait">
          {authStatus === 'loading' ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.24, ease: [0.4, 0, 0.2, 1] }}
              className="absolute inset-0 flex flex-col items-center justify-center bg-canvas z-50"
            >
              <motion.div
                className="flex flex-col items-center gap-7"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="bg-surface border-hairline-strong flex h-16 w-16 items-center justify-center rounded-2xl border shadow-[0_8px_24px_rgba(0,0,0,0.32)]">
                  <TelegramLogo className="text-primary h-8 w-8" />
                </div>

                <div className="flex flex-col items-center gap-3">
                  <h2 className="text-foreground text-[22px] font-semibold tracking-tight">
                    Telegrab
                  </h2>
                  <div className="flex items-center gap-1.5">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="bg-primary/80 dot-pulse h-1 w-1 rounded-full"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                </div>
              </motion.div>
            </motion.div>
          ) : (
            <motion.div
              key="content"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
              className="flex-1 flex flex-col min-h-0"
            >
              {authStatus === 'authenticated' ? (
                <Dashboard onLogout={() => setAuthStatus('unauthenticated')} />
              ) : (
                <Suspense fallback={null}>
                  <AuthWizard onLogin={() => setAuthStatus('authenticated')} />
                </Suspense>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
    </>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={200}>
          <ConfirmProvider>
            <SettingsProvider>
              <UpdateProvider>
                <AppContent />
              </UpdateProvider>
            </SettingsProvider>
          </ConfirmProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
