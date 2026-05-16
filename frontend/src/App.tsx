import { useState, useEffect } from 'react';
import { invoke } from './lib/platform/core';
import { load } from './lib/platform/store';
import { listen } from './lib/platform/event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthWizard } from './components/AuthWizard';
import { Dashboard } from './components/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { motion, AnimatePresence } from 'framer-motion';

import { TitleBar } from './components/TitleBar';
import './styles/globals.css';

import { Toaster } from 'sonner';
import { ConfirmProvider } from './contexts/ConfirmContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { DropZoneProvider } from './contexts/DropZoneContext';

const queryClient = new QueryClient();

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

const TelegramLogo = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 512 512"
    fill="currentColor"
    className={className}
  >
    <path d="M512 256C512 114.62 397.38 0 256 0S0 114.62 0 256s114.62 256 256 256 256-114.62 256-256zm-396.12-2.7c74.63-32.52 124.39-53.95 149.29-64.31 71.1-29.57 85.87-34.71 95.5-34.88 2.12-.03 6.85.49 9.92 2.98 2.59 2.1 3.3 4.94 3.64 6.93.34 2 .77 6.53.43 10.08-3.85 40.48-20.52 138.71-29 184.05-3.59 19.19-10.66 25.62-17.5 26.25-14.86 1.37-26.15-9.83-40.55-19.27-22.53-14.76-35.26-23.96-57.13-38.37-25.28-16.66-8.89-25.81 5.51-40.77 3.77-3.92 69.27-63.5 70.54-68.9.16-.68.31-3.2-1.19-4.53s-3.71-.87-5.3-.51c-2.26.51-38.25 24.3-107.98 71.37-10.22 7.02-19.48 10.43-27.77 10.26-9.14-.2-26.72-5.17-39.79-9.42-16.03-5.21-28.77-7.97-27.66-16.82.57-4.61 6.92-9.32 19.04-14.14z" />
  </svg>
);

function AppContent() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading');

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
        }, 1200);
      } catch (err) {
        console.warn('Session restore failed, showing login:', err);
        setAuthStatus('unauthenticated');
      }
    };

    checkSession();
  }, []);

  const [isMaximized, setIsMaximized] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    const setup = async () => {
      unlisten = await listen<boolean>('window-maximized', (event) => {
        setIsTransitioning(true);
        setIsMaximized(event.payload);
        setTimeout(() => setIsTransitioning(false), 500);
      });
    };
    setup();
    return () => unlisten?.();
  }, []);

  return (
    <main 
      className={`text-foreground selection:bg-primary/30 relative flex h-screen w-screen flex-col overflow-hidden bg-canvas ${
        isMaximized ? 'rounded-none' : 'rounded-xl'
      } transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]`}
    >
      <TitleBar />
      <div className={`flex-1 flex flex-col min-h-0 ${isTransitioning ? 'window-content-scale opacity-80 blur-[2px] scale-[0.995]' : 'window-content-scale'}`}>
        <Toaster
          theme="dark"
          position="bottom-center"
          toastOptions={{
            style: {
              background: 'var(--color-surface)',
              backdropFilter: 'blur(12px)',
              border: '1px solid var(--color-hairline)',
              color: 'var(--color-ink)',
            },
          }}
        />
        
        <AnimatePresence mode="wait">
          {authStatus === 'loading' ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, scale: 1.05, filter: 'blur(20px)' }}
              transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
              className="absolute inset-0 flex flex-col items-center justify-center bg-canvas z-50 overflow-hidden"
            >
              {/* Ambient Background Pulse */}
              <motion.div 
                className="bg-primary/10 absolute inset-0 -z-10 blur-[120px]"
                animate={{ 
                  scale: [1, 1.2, 1],
                  opacity: [0.3, 0.5, 0.3]
                }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
              />

              <motion.div 
                className="flex flex-col items-center gap-10"
                initial={{ y: 30, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.2, duration: 1, type: 'spring', bounce: 0.3 }}
              >
                <div className="relative group">
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0, rotate: -10 }}
                    animate={{ scale: 1, opacity: 1, rotate: 0 }}
                    transition={{ 
                      type: 'spring',
                      stiffness: 200,
                      damping: 25,
                      delay: 0.3
                    }}
                    className="auth-glass border-white/10 flex h-28 w-28 items-center justify-center rounded-[2.5rem] shadow-[0_20px_50px_rgba(0,0,0,0.5)] relative z-10 overflow-hidden"
                  >
                    <TelegramLogo className="text-white w-14 h-14 drop-shadow-2xl" />
                    
                    {/* Shimmer Effect */}
                    <motion.div 
                      className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/20 to-transparent -translate-x-full"
                      animate={{ translateX: ['100%', '-100%'] }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear", repeatDelay: 1 }}
                    />
                  </motion.div>
                  
                  <motion.div 
                    className="bg-primary/30 absolute -inset-8 -z-10 rounded-full blur-3xl"
                    animate={{ 
                      scale: [1, 1.3, 1],
                      opacity: [0.2, 0.4, 0.2]
                    }}
                    transition={{ 
                      duration: 5, 
                      repeat: Infinity,
                      ease: "easeInOut" 
                    }}
                  />
                </div>

                <div className="flex flex-col items-center gap-4">
                  <motion.h2 
                    className="text-white text-4xl font-bold tracking-tighter"
                    initial={{ opacity: 0, letterSpacing: "-0.05em" }}
                    animate={{ opacity: 1, letterSpacing: "0em" }}
                    transition={{ delay: 0.5, duration: 0.8 }}
                  >
                    Telegrab
                  </motion.h2>
                  
                  <motion.div 
                    className="flex flex-col items-center gap-3"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.8 }}
                  >
                    <div className="flex gap-2">
                      {[0, 1, 2].map((i) => (
                        <motion.div
                          key={i}
                          className="h-1.5 w-1.5 rounded-full bg-primary"
                          animate={{ 
                            scale: [1, 1.5, 1],
                            opacity: [0.3, 1, 0.3],
                            boxShadow: ["0 0 0px var(--color-primary)", "0 0 8px var(--color-primary)", "0 0 0px var(--color-primary)"]
                          }}
                          transition={{ 
                            duration: 1.5, 
                            repeat: Infinity, 
                            delay: i * 0.2 
                          }}
                        />
                      ))}
                    </div>
                    <span className="text-stone/60 text-[11px] font-semibold uppercase tracking-[0.2em]">
                      Initializing secure environment
                    </span>
                  </motion.div>
                </div>
              </motion.div>
            </motion.div>
          ) : (
            <motion.div
              key="content"
              initial={{ opacity: 0, scale: 0.98, filter: 'blur(10px)' }}
              animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="flex-1 flex flex-col min-h-0"
            >
              {authStatus === 'authenticated' ? (
                <Dashboard onLogout={() => setAuthStatus('unauthenticated')} />
              ) : (
                <AuthWizard onLogin={() => setAuthStatus('authenticated')} />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ConfirmProvider>
          <SettingsProvider>
            <DropZoneProvider>
              <AppContent />
            </DropZoneProvider>
          </SettingsProvider>
        </ConfirmProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
