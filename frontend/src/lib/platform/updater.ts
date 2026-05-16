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

export type DownloadEvent =
  | { event: "Started"; data: { contentLength?: number } }
  | { event: "Progress"; data: { chunkLength?: number } }
  | { event: "Finished"; data?: undefined };

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
  return null;
}
