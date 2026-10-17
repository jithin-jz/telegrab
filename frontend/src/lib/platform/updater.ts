/**
 * Desktop platform auto-updater.
 *
 * `check()` asks the Python updater for the latest release and returns an
 * `Update` object if a newer version is available, or `null` otherwise.
 *
 * The backend resolves and verifies the installer itself; installing never
 * sends a URL or checksum from the webview. When `manual` is true (macOS /
 * Linux) "installing" opens the release page in the browser instead.
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
  /** True when the update must be downloaded from the release page. */
  manual: boolean;
  downloadAndInstall(onEvent?: DownloadProgressCallback): Promise<void>;
}

interface CheckResult {
  available: boolean;
  version?: string;
  date?: string;
  body?: string;
  manual?: boolean;
}

interface UpdateProgressDetail {
  event: 'Started' | 'Progress';
  total?: number;
  chunk?: number;
}

export async function check(): Promise<Update | null> {
  const res = await invoke<CheckResult | null>('cmd_check_for_updates');
  if (!res || !res.available || !res.version) return null;

  return {
    version: res.version,
    date: res.date,
    body: res.body,
    manual: !!res.manual,
    downloadAndInstall: async (onEvent) => {
      const handler = (e: Event) => {
        const detail = (e as CustomEvent<UpdateProgressDetail>).detail;
        if (!onEvent || !detail) return;
        if (detail.event === 'Started') {
          onEvent({ event: 'Started', data: { contentLength: detail.total } });
        } else if (detail.event === 'Progress') {
          onEvent({ event: 'Progress', data: { chunkLength: detail.chunk } });
        }
      };
      window.addEventListener('updateProgress', handler);
      try {
        await invoke('cmd_download_and_install_update');
      } finally {
        window.removeEventListener('updateProgress', handler);
      }
    },
  };
}
