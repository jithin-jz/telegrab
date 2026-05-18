import { useState, useEffect, useRef } from 'react';
import { invoke } from '../lib/platform/core';

/**
 * Network detection using lightweight backend TCP check to Telegram servers.
 * Polls every 10 seconds (~2ms per check).
 */
export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const checkNetwork = async () => {
      try {
        const available = await invoke<boolean>('cmd_is_network_available');
        if (mountedRef.current) setIsOnline(available);
      } catch {
        if (mountedRef.current) setIsOnline(false);
      }
    };

    checkNetwork();
    const interval = setInterval(checkNetwork, 10_000);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, []);

  return isOnline;
}
