import { invoke } from './platform/core';
import { formatBytes } from './utils';
import { TelegramFile } from '../types';

export async function fetchFiles(folderId: number | null): Promise<TelegramFile[]> {
  const res = await invoke<any[]>('cmd_get_files', { folderId });
  return res.map((f) => ({
    ...f,
    sizeStr: formatBytes(f.size),
    type: f.icon_type || (f.name.endsWith('/') ? 'folder' : 'file'),
  }));
}
