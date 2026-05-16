/**
 * Shim for `@tauri-apps/plugin-updater`.
 *
 * Auto-update is not part of the pywebview build. `check()` resolves to
 * `null` so the existing `useUpdateCheck` hook gracefully treats the
 * app as up to date.
 *
 * The exported types mirror the real plugin's shape so callers that pass
 * a progress callback to `downloadAndInstall(...)` still type-check.
 */

import { invoke } from './core';

export type DownloadEvent =
  | { event: 'Started'; data: { contentLength?: number } }
  | { event: 'Progress'; data: { chunkLength?: number } }
  | { event: 'Finished'; data?: undefined };

export type DownloadProgressCallback = (event: DownloadEvent) => void;

export interface Update {
  version: string;
  date?: string;
  body?: string;
  download(onEvent?: DownloadProgressCallback): Promise<void>;
  install(): Promise<void>;
  downloadAndInstall(onEvent?: DownloadProgressCallback): Promise<void>;
}

export async function check(): Promise<Update | null> {
  try {
    const res = await invoke<any>('cmd_check_for_updates');
    if (!res || !res.available) return null;

    return {
      version: res.version,
      date: res.date,
      body: res.body,
      download: async () => {}, // unused
      install: async () => {}, // unused
      downloadAndInstall: async (onEvent) => {
        const handler = (e: any) => {
          if (onEvent && e.detail) {
            if (e.detail.event === 'Started') {
              onEvent({ event: 'Started', data: { contentLength: e.detail.total } });
            } else if (e.detail.event === 'Progress') {
              onEvent({ event: 'Progress', data: { chunkLength: e.detail.chunk } });
            }
          }
        };
        window.addEventListener('updateProgress', handler);
        try {
          await invoke('cmd_download_and_install_update', { url: res.download_url });
        } finally {
          window.removeEventListener('updateProgress', handler);
        }
      },
    };
  } catch (err) {
    console.error('Update check failed:', err);
    return null;
  }
}
