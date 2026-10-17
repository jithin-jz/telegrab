import { createContext, useContext, type ReactNode } from 'react';
import { useNetworkPoller } from '../hooks/useNetworkPoller';

/**
 * Single source of truth for connectivity.
 *
 * The poller must run exactly once per app: every extra instance would add
 * its own TCP probes and emit its own `network-restored` event (resuming
 * paused transfers several times over).
 */
const NetworkStatusContext = createContext<boolean | undefined>(undefined);

export function NetworkStatusProvider({ children }: { children: ReactNode }) {
  const isOnline = useNetworkPoller();
  return <NetworkStatusContext.Provider value={isOnline}>{children}</NetworkStatusContext.Provider>;
}

export function useNetworkStatus(): boolean {
  const value = useContext(NetworkStatusContext);
  if (value === undefined) {
    throw new Error('useNetworkStatus must be used within a NetworkStatusProvider');
  }
  return value;
}
