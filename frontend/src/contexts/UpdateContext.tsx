import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';
import { check, type Update } from '../lib/platform/updater';
import { toast } from 'sonner';

interface UpdateState {
  checking: boolean;
  available: boolean;
  downloading: boolean;
  progress: number;
  error: string | null;
  version: string | null;
}

interface UpdateContextValue extends UpdateState {
  checkForUpdates: () => Promise<void>;
  downloadAndInstall: () => Promise<void>;
  dismissUpdate: () => void;
}

const UpdateContext = createContext<UpdateContextValue | null>(null);

export function UpdateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UpdateState>({
    checking: false,
    available: false,
    downloading: false,
    progress: 0,
    error: null,
    version: null,
  });
  const updateRef = useRef<Update | null>(null);
  const checkingRef = useRef(false);

  const checkForUpdates = useCallback(async () => {
    // Prevent concurrent checks
    if (checkingRef.current) return;
    checkingRef.current = true;
    setState((s) => ({ ...s, checking: true, error: null }));
    try {
      const updateInfo = await check();
      if (updateInfo) {
        updateRef.current = updateInfo;
        setState((s) => ({ ...s, checking: false, available: true, version: updateInfo.version }));
      } else {
        setState((s) => ({ ...s, checking: false, available: false }));
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to check for updates';
      toast.error(message);
      setState((s) => ({ ...s, checking: false, error: message }));
    } finally {
      checkingRef.current = false;
    }
  }, []);

  const downloadAndInstall = useCallback(async () => {
    const update = updateRef.current;
    if (!update) return;

    setState((s) => ({ ...s, downloading: true, progress: 0, error: null }));
    let downloaded = 0;
    let contentLength = 0;

    try {
      await update.downloadAndInstall((event) => {
        if (event.event === 'Started') {
          contentLength = (event.data as { contentLength?: number }).contentLength || 0;
        } else if (event.event === 'Progress') {
          downloaded += (event.data as { chunkLength?: number }).chunkLength || 0;
          if (contentLength > 0) {
            const pct = Math.round((downloaded / contentLength) * 100);
            setState((s) => ({ ...s, progress: Math.min(pct, 100) }));
          }
        }
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to install update';
      toast.error(message);
      setState((s) => ({ ...s, downloading: false, error: message }));
    }
  }, []);

  const dismissUpdate = useCallback(() => {
    setState((s) => ({ ...s, available: false }));
    updateRef.current = null;
  }, []);

  return (
    <UpdateContext.Provider value={{ ...state, checkForUpdates, downloadAndInstall, dismissUpdate }}>
      {children}
    </UpdateContext.Provider>
  );
}

export function useUpdate(): UpdateContextValue {
  const ctx = useContext(UpdateContext);
  if (!ctx) throw new Error('useUpdate must be used within UpdateProvider');
  return ctx;
}
