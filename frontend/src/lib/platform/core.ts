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
export interface BridgeInitError {
  __error: true;
  code: string;
  message: string;
  detail: string;
}

/**
 * Invoke a backend command.
 *
 * The backend exposes command names on `window.pywebview.api.cmd_x` and accepts a
 * single args object.
 *
 * Calls are transparently queued if pywebview hasn't finished injecting its API.
 * The queue retries at 50 ms intervals for up to 10 seconds. After that, the call
 * rejects with a BRIDGE_NOT_READY error.
 */
export async function invoke<T = unknown>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await callPy<T>(cmd, args);
  } catch (err: unknown) {
    if (err instanceof Error && err.message.includes('pywebview API never became available')) {
      const initError: BridgeInitError = {
        __error: true,
        code: 'BRIDGE_NOT_READY',
        message: 'Backend initialization timed out. Please restart the application.',
        detail:
          'The pywebview API did not become available within 10 seconds. ' +
          'This usually means the Python backend failed to start or is unresponsive.',
      };
      throw initError;
    }
    throw err;
  }
}

/**
 * Convert a local file path into a URL the webview can load.
 *
 * pywebview can load `file://` URLs directly when
 * `webview.settings['ALLOW_FILE_URLS']` is true, which we set in `app.py`.
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
