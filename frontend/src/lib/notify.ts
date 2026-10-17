import { toast } from 'sonner';
import { invoke } from './platform/core';
import type { NotificationStyle } from '../contexts/SettingsContext';

/**
 * Report a completed background action (e.g. a finished transfer) the way
 * the user asked for in Settings → Notifications. Errors always use toasts:
 * they need attention regardless of this preference.
 */
export function notifyDone(style: NotificationStyle, message: string): void {
  if (style === 'none') return;
  if (style === 'system') {
    invoke<boolean>('cmd_notify', { title: 'Telegrab', message })
      .then((shown) => {
        if (!shown) toast.success(message);
      })
      .catch(() => toast.success(message));
    return;
  }
  toast.success(message);
}
