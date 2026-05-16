/**
 * Shim for `@tauri-apps/api/core`.
 *
 * Re-implements `invoke` and `convertFileSrc` on top of `window.pywebview.api`.
 */

import { callPy } from './internal';

/**
 * Invoke a backend command. Drop-in replacement for Tauri's `invoke`.
 *
 * Tauri called `invoke('cmd_x', {foo, bar})`. Our backend exposes the
 * exact same command names on `window.pywebview.api.cmd_x` and accepts a
 * single args object.
 */
export function invoke<T = unknown>(
  cmd: string,
  args?: Record<string, unknown>
): Promise<T> {
  return callPy<T>(cmd, args);
}

/**
 * Convert a local file path into a URL the webview can load.
 *
 * Tauri served local files via `tauri://localfile/...`; pywebview can load
 * `file://` URLs directly when `webview.settings['ALLOW_FILE_URLS']` is true,
 * which we set in `app.py`.
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
