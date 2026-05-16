/**
 * Shim for `@tauri-apps/plugin-shell`.
 *
 * Only `open(url)` is used by the React app — it's invoked when the user
 * clicks an external link (e.g. the my.telegram.org instructions).
 */

import { callPy } from './internal';

export async function open(target: string, _openWith?: string): Promise<void> {
  await callPy<boolean>('cmd_shell_open', { target });
}

/** `Command` is referenced by the original plugin's type exports, stub it out. */
export class Command {
  constructor(_program: string, _args?: string[]) {
    throw new Error('Command execution is not supported in the Python backend');
  }
}
