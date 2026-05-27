import { invoke } from './platform/core';
import { formatBytes } from './utils';
import { TelegramFile } from '../types';

/**
 * Paginated response shape for file fetching.
 * Currently the backend returns all files at once (nextOffsetId is always undefined).
 * When the backend adds pagination support (e.g. cmd_get_files accepts offset_id + limit),
 * update this function to pass those params and return the cursor from the response.
 */
export interface FilePage {
  files: TelegramFile[];
  /** The offset ID for the next page. `undefined` means no more pages. */
  nextOffsetId: number | undefined;
}

export async function fetchFiles(
  folderId: number | null,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _offsetId?: number,
): Promise<FilePage> {
  // TODO: When backend supports pagination, pass offsetId and limit:
  // const res = await invoke<{ files: any[]; next_offset_id?: number }>(
  //   'cmd_get_files', { folderId, offsetId, limit: 50 }
  // );
  // For now, backend returns all files in one shot.
  const res = await invoke<any[]>('cmd_get_files', { folderId });
  const files: TelegramFile[] = res.map((f) => ({
    ...f,
    sizeStr: formatBytes(f.size),
    type: f.icon_type || (f.name.endsWith('/') ? 'folder' : 'file'),
  }));

  return {
    files,
    // No pagination from backend yet — always signals "no more pages"
    nextOffsetId: undefined,
  };
}
