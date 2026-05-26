/**
 * Desktop platform process control — relaunch and exit.
 */

import { callPy } from './internal';

export async function relaunch(): Promise<void> {
  await callPy<void>('cmd_relaunch');
}

export async function exit(_code = 0): Promise<void> {
  // Closing the window is the cleanest way to exit a pywebview app.
  // Trigger via the same backend method (which os.execv-restarts), then
  // fall back to closing the page if no Python is reachable.
  try {
    window.close();
  } catch {
    /* ignore */
  }
}
