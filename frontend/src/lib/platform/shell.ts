/**
 * Desktop platform shell — open URLs and files with the OS default handler.
 */

import { invoke } from './core';

/** Drop-in replacement for Tauri's `open(url)`. */
export async function open(target: string): Promise<void> {
  await invoke('cmd_shell_open', { target });
}
