import { invoke } from '../lib/platform/core';

export interface DuplicateResult {
  duplicate: boolean;
  hash: string;
  existing: { message_id: number; folder_id?: number | null; name: string; size: number } | null;
}

export async function checkDuplicate(
  path: string,
  folderId: number | null
): Promise<DuplicateResult> {
  return invoke<DuplicateResult>('cmd_check_duplicate', { path, folderId });
}
