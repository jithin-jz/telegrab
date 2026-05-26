/**
 * Desktop platform auto-updater.
 *
 * `check()` calls the Python updater service and returns an `Update` object
 * if a newer version is available, or `null` if the app is up to date.
 *
 * The exported types mirror the expected shape so callers that pass
 * a progress callback to `downloadAndInstall(...)` type-check correctly.
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
          await invoke('cmd_download_and_install_update', { url: res.download_url, sha256: res.sha256 || '' });
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
