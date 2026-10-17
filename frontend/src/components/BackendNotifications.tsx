import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { listen, type UnlistenFn } from '../lib/platform/event';

interface ToastPayload {
  type: 'fatal' | 'recovery' | string;
  title: string;
  message: string;
}

/** Minimum gap between repeated rate-limit toasts (ms). */
const RATE_LIMIT_TOAST_INTERVAL = 30_000;

/**
 * Surfaces events the backend pushes without a matching request:
 * runtime recovery/fatal notices, Telegram rate limits, and vault auto-lock.
 * Renders nothing.
 */
export function BackendNotifications() {
  const queryClient = useQueryClient();
  const lastRateLimitToast = useRef(0);

  useEffect(() => {
    const unlisteners: Promise<UnlistenFn>[] = [
      listen<ToastPayload>('toast', ({ payload }) => {
        if (payload.type === 'fatal') {
          toast.error(payload.title, { description: payload.message, duration: Infinity });
        } else {
          toast.success(payload.title, { description: payload.message });
        }
      }),
      listen<{ wait_seconds: number }>('rate-limited', ({ payload }) => {
        const now = Date.now();
        if (now - lastRateLimitToast.current < RATE_LIMIT_TOAST_INTERVAL) return;
        lastRateLimitToast.current = now;
        const secs = Math.ceil(payload.wait_seconds);
        toast.warning('Telegram rate limit', {
          description: `Transfers will continue automatically in about ${secs}s.`,
        });
      }),
      listen<{ folderId: number }>('vault-locked', ({ payload }) => {
        queryClient.invalidateQueries({ queryKey: ['vault', payload.folderId] });
        toast.info('Vault locked after inactivity');
      }),
    ];
    return () => {
      unlisteners.forEach((p) => p.then((un) => un()));
    };
  }, [queryClient]);

  return null;
}
