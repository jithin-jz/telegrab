/**
 * Desktop platform core — invoke & file-src helpers.
 *
 * Implements `invoke` and `convertFileSrc` on top of `window.pywebview.api`.
 *
 * If the pywebview API is not yet available when `invoke` is called, the call is
 * queued internally and retried at 50 ms intervals for up to 10 seconds. If the
 * backend still hasn't become available after that window, the promise rejects
 * with a structured initialization error (BRIDGE_NOT_READY).
 */

import { callPy } from './internal';

/** Structured error matching the BridgeError contract from the backend. */
export interface BridgeErrorPayload {
  __error: true;
  code: string;
  message: string;
  detail: string;
}

/** @deprecated Use {@link BridgeErrorPayload}. */
export type BridgeInitError = BridgeErrorPayload;

/**
 * Error thrown by {@link invoke} when a backend command fails.
 *
 * `message` is safe to show to users; `code` is machine-readable
 * (e.g. `TELEGRAM_NOT_CONNECTED`, `VAULT_WRONG_PASSWORD`).
 */
export class BridgeCommandError extends Error {
  readonly code: string;
  readonly detail: string;

  constructor(payload: Pick<BridgeErrorPayload, 'code' | 'message' | 'detail'>) {
    super(payload.message || payload.code || 'Backend error');
    this.name = 'BridgeCommandError';
    this.code = payload.code;
    this.detail = payload.detail;
  }

  // `String(err)` is used throughout the UI — keep it to the user message.
  toString(): string {
    return this.message;
  }
}

function isErrorPayload(value: unknown): value is BridgeErrorPayload {
  return !!value && typeof value === 'object' && (value as { __error?: unknown }).__error === true;
}

/** Human-readable message for any thrown value. */
export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (isErrorPayload(err)) return err.message;
  return String(err);
}

/**
 * Invoke a backend command.
 *
 * The backend exposes command names on `window.pywebview.api.cmd_x` and accepts a
 * single args object. Failures are returned by the backend as a structured
 * error payload and re-thrown here as a {@link BridgeCommandError}.
 *
 * Calls are transparently queued if pywebview hasn't finished injecting its API.
 * The queue retries at 50 ms intervals for up to 10 seconds. After that, the call
 * rejects with a BRIDGE_NOT_READY error.
 */
export async function invoke<T = unknown>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  let result: T;
  try {
    result = await callPy<T>(cmd, args);
  } catch (err: unknown) {
    if (err instanceof Error && err.message.includes('pywebview API never became available')) {
      throw new BridgeCommandError({
        code: 'BRIDGE_NOT_READY',
        message: 'Backend initialization timed out. Please restart the application.',
        detail:
          'The pywebview API did not become available within 10 seconds. ' +
          'This usually means the Python backend failed to start or is unresponsive.',
      });
    }
    throw err;
  }
  if (isErrorPayload(result)) {
    throw new BridgeCommandError(result);
  }
  return result;
}

/**
 * Convert a local file path into a URL the webview can load.
 *
 * The production bundle is loaded from `file://`, so local files (e.g. large
 * cached previews) can be referenced directly.
 */
export function convertFileSrc(filePath: string, _protocol = 'asset'): string {
  if (!filePath) return filePath;
  if (
    filePath.startsWith('http://') ||
    filePath.startsWith('https://') ||
    filePath.startsWith('data:') ||
    filePath.startsWith('file://')
  ) {
    return filePath;
  }
  // Normalise Windows backslashes.
  const normalized = filePath.replace(/\\/g, '/');
  // file:// URI: prepend a slash for Windows drive letters (C:/...).
  if (/^[a-zA-Z]:/.test(normalized)) {
    return `file:///${encodeURI(normalized)}`;
  }
  return `file://${encodeURI(normalized)}`;
}
