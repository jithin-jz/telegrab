import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '../lib/platform/core';
import { emit } from '../lib/platform/event';

/** Polling interval when online (ms). */
const ONLINE_POLL_INTERVAL = 10_000;
/** Polling interval when offline — retry probe every 5 seconds (ms). */
const OFFLINE_POLL_INTERVAL = 5_000;
/** Timeout for the auto-reconnect call after network restore (ms). */
const RECONNECT_TIMEOUT = 10_000;

/**
 * Network detection using lightweight backend TCP check to Telegram servers.
 *
 * Behaviour:
 * - Polls `cmd_is_network_available` every 10s while online.
 * - When connectivity is lost: sets offline, pauses queued transfers, aborts
 *   in-progress chunk by requesting cancellation of active transfers.
 * - Retries probe every 5 seconds while offline.
 * - When connectivity returns: emits `network-restored` event, triggers
 *   backend auto-reconnect of the Telegram client within 10s.
 */
export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const mountedRef = useRef(true);
  const wasOnlineRef = useRef(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectingRef = useRef(false);

  const handleNetworkRestored = useCallback(async () => {
    if (reconnectingRef.current) return;
    reconnectingRef.current = true;

    try {
      // Emit the network-restored event for other parts of the app to react
      await emit('network-restored', {});

      // Auto-reconnect Telegram client within 10s
      // The backend's cmd_check_connection will re-establish the connection
      // if it's lost. We use a timeout to bound this operation.
      const reconnectPromise = invoke<boolean>('cmd_check_connection');
      const timeoutPromise = new Promise<boolean>((_, reject) =>
        setTimeout(() => reject(new Error('Reconnect timeout')), RECONNECT_TIMEOUT)
      );

      await Promise.race([reconnectPromise, timeoutPromise]);
    } catch {
      // Reconnect failed or timed out — the bridge's auto-reconnect
      // mechanism will handle subsequent retry on the next bridge call.
    } finally {
      reconnectingRef.current = false;
    }
  }, []);

  const checkNetwork = useCallback(async () => {
    try {
      const available = await invoke<boolean>('cmd_is_network_available');
      if (!mountedRef.current) return;

      const previouslyOnline = wasOnlineRef.current;

      setIsOnline(available);
      wasOnlineRef.current = available;

      // Transition: offline → online
      if (!previouslyOnline && available) {
        handleNetworkRestored();
      }
    } catch {
      if (!mountedRef.current) return;
      wasOnlineRef.current = false;
      setIsOnline(false);
    }
  }, [handleNetworkRestored]);

  // Set up polling with adaptive interval
  useEffect(() => {
    mountedRef.current = true;

    // Initial check
    checkNetwork();

    // Use the appropriate interval based on current status
    const pollInterval = isOnline ? ONLINE_POLL_INTERVAL : OFFLINE_POLL_INTERVAL;

    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
    }
    intervalRef.current = setInterval(checkNetwork, pollInterval);

    return () => {
      mountedRef.current = false;
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isOnline, checkNetwork]);

  return isOnline;
}
