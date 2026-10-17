import { invoke } from './platform/core';
import { formatBytes } from './utils';
import { TelegramFile } from '../types';

/**
 * Paginated response shape for file fetching.
 */
export interface FilePage {
  files: TelegramFile[];
  /** The offset ID for the next page. `undefined` means no more pages. */
  nextOffsetId: number | undefined;
}

interface RawFile {
  id: number;
  folder_id?: number | null;
  name: string;
  size: number;
  created_at?: string;
  icon_type?: string;
  mime_type?: string | null;
  file_ext?: string | null;
}

interface RawFilePage {
  files: RawFile[];
  next_offset_id: number;
}

export const PAGE_LIMIT = 100;

export function toTelegramFile(f: RawFile): TelegramFile {
  return {
    ...f,
    sizeStr: formatBytes(f.size),
    type: f.icon_type === 'folder' || f.name.endsWith('/') ? 'folder' : 'file',
  };
}

export async function fetchFiles(
  folderId: number | null,
  offsetId?: number,
): Promise<FilePage> {
  const res = await invoke<RawFilePage>('cmd_get_files', {
    folderId,
    offsetId: offsetId ?? 0,
    limit: PAGE_LIMIT,
  });
  return {
    files: res.files.map(toTelegramFile),
    // The backend's cursor is the last *message* scanned, so pages that
    // contain non-file messages don't end pagination early. 0 = no more.
    nextOffsetId: res.next_offset_id > 0 ? res.next_offset_id : undefined,
  };
}

/** Search Saved Messages plus the given Telegrab folders by file name. */
export async function searchFiles(query: string, folderIds: number[]): Promise<TelegramFile[]> {
  const res = await invoke<RawFile[]>('cmd_search_global', { query, folderIds });
  return res.map(toTelegramFile);
}

/** Stable identity of a file across folders (message ids restart per folder). */
export function fileKey(file: Pick<TelegramFile, 'id' | 'folder_id'>, fallbackFolder: number | null): string {
  const folder = file.folder_id === undefined ? fallbackFolder : file.folder_id;
  return `${folder ?? 'home'}:${file.id}`;
}

/** Folder a file belongs to: its own (search results) or the open folder. */
export function folderOf(
  file: Pick<TelegramFile, 'folder_id'>,
  fallbackFolder: number | null | undefined,
): number | null {
  return file.folder_id === undefined ? (fallbackFolder ?? null) : file.folder_id;
}
