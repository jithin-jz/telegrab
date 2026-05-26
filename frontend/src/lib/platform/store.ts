/**
 * Desktop platform key-value store.
 *
 * Implements a `Store` class that forwards calls to the pywebview bridge.
 */

import { invoke } from './core';

export class Store {
  constructor(public path: string) {}

  async get<T>(key: string): Promise<T | null> {
    return invoke<T | null>('cmd_store_get', { key });
  }

  async set(key: string, value: unknown): Promise<void> {
    await invoke('cmd_store_set', { key, value });
  }

  async delete(key: string): Promise<boolean> {
    return invoke<boolean>('cmd_store_delete', { key });
  }

  async entries<T>(): Promise<[string, T][]> {
    const res = await invoke<Record<string, T>>('cmd_store_entries');
    return Object.entries(res);
  }

  /** In pywebview, saving is usually automatic or handled in set(), but we stub it. */
  async save(): Promise<void> {
    // No-op or potentially a cmd_store_save if the backend needs explicit flushing.
  }
}

/** Drop-in replacement for Tauri's `load(path)`. */
export async function load(path: string): Promise<Store> {
  return new Store(path);
}
