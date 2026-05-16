/**
 * Shim for `@tauri-apps/plugin-store`.
 *
 * Replicates the surface the React code uses:
 *
 *   const store = await load('app_settings.dat');
 *   await store.get<string>('api_id');
 *   await store.set('settings', value);
 *   await store.delete('api_id');
 *   await store.save();
 *
 * Persistence happens implicitly on every set/delete on the Python side, so
 * `save()` here is a no-op — preserved purely for API compatibility.
 */

import { callPy } from './internal';

export class Store {
  // The original Tauri Store was per-file; we collapse to a single backing
  // JSON file (`paths.store_path()`) and keep `path` purely for compatibility
  // with code that introspects `store.path`.
  readonly path: string;

  private constructor(path: string) {
    this.path = path;
  }

  static async load(path: string): Promise<Store> {
    return new Store(path);
  }

  async get<T = unknown>(key: string): Promise<T | undefined> {
    const v = await callPy<unknown>('cmd_store_get', { key });
    return (v ?? undefined) as T | undefined;
  }

  async set(key: string, value: unknown): Promise<void> {
    await callPy<boolean>('cmd_store_set', { key, value });
  }

  async delete(key: string): Promise<boolean> {
    return await callPy<boolean>('cmd_store_delete', { key });
  }

  /** Persistence is automatic — exists for API compatibility. */
  async save(): Promise<void> {
    return;
  }

  async entries<T = unknown>(): Promise<[string, T][]> {
    const obj = await callPy<Record<string, unknown>>('cmd_store_entries');
    return Object.entries(obj || {}) as [string, T][];
  }

  async keys(): Promise<string[]> {
    const obj = await callPy<Record<string, unknown>>('cmd_store_entries');
    return Object.keys(obj || {});
  }

  async values<T = unknown>(): Promise<T[]> {
    const obj = await callPy<Record<string, unknown>>('cmd_store_entries');
    return Object.values(obj || {}) as T[];
  }

  async length(): Promise<number> {
    return (await this.keys()).length;
  }

  async has(key: string): Promise<boolean> {
    const v = await this.get<unknown>(key);
    return v !== undefined && v !== null;
  }

  async clear(): Promise<void> {
    const keys = await this.keys();
    await Promise.all(keys.map((k) => this.delete(k)));
  }
}

/** `load(path)` factory matches the original Tauri `plugin-store` API. */
export function load(path: string): Promise<Store> {
  return Store.load(path);
}

export default Store;
