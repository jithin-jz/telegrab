// Connectivity is provided app-wide by NetworkStatusProvider; see
// contexts/NetworkStatusContext.tsx for why it must not be polled per component.
export { useNetworkStatus } from '../contexts/NetworkStatusContext';
