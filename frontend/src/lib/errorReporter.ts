/**
 * Global uncaught error forwarding.
 *
 * Registers window-level listeners for `error` (uncaught exceptions) and
 * `unhandledrejection` (unhandled promise rejections). Each captured error is
 * formatted with its message and stack trace, truncated to 2000 characters, and
 * forwarded to the backend via `cmd_log` for diagnostic purposes.
 *
 * Call `setupGlobalErrorForwarding()` once, early in app initialization.
 */

import { invoke } from './platform/core';

const MAX_LOG_LENGTH = 2000;

/**
 * Format an error into a loggable string, truncated to 2000 chars.
 */
function formatError(prefix: string, message: string, stack?: string): string {
  const parts = [prefix, `Message: ${message}`];
  if (stack) {
    parts.push(`Stack: ${stack}`);
  }
  return parts.join('\n').slice(0, MAX_LOG_LENGTH);
}

/**
 * Forward a formatted error message to the backend.
 * Failures are silently swallowed — if the backend is unreachable we can't do anything.
 */
function forwardToBackend(logMessage: string): void {
  invoke('cmd_log', { message: logMessage }).catch(() => {
    // Swallow — backend may not be available
  });
}

/**
 * Register global error handlers that forward uncaught JS errors
 * and unhandled promise rejections to the backend via `cmd_log`.
 *
 * Should be called once at app startup before rendering.
 */
export function setupGlobalErrorForwarding(): void {
  // Catch uncaught synchronous exceptions
  window.addEventListener('error', (event: ErrorEvent) => {
    const message = event.error?.message || event.message || 'Unknown error';
    const stack = event.error?.stack || '';
    const logMessage = formatError('[UncaughtError]', message, stack);
    forwardToBackend(logMessage);
  });

  // Catch unhandled promise rejections
  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    let message: string;
    let stack: string | undefined;

    if (event.reason instanceof Error) {
      message = event.reason.message;
      stack = event.reason.stack;
    } else if (typeof event.reason === 'string') {
      message = event.reason;
    } else {
      try {
        message = JSON.stringify(event.reason);
      } catch {
        message = String(event.reason);
      }
    }

    const logMessage = formatError('[UnhandledRejection]', message, stack);
    forwardToBackend(logMessage);
  });
}
