/**
 * Shim for `@tauri-apps/plugin-shell`.
 */

import { invoke } from './core';

/** Drop-in replacement for Tauri's `open(url)`. */
export async function open(target: string): Promise<void> {
  await invoke('cmd_shell_open', { target });
}
