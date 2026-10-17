import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Api = Record<string, (args?: unknown) => Promise<unknown>>;

function installApi(api: Api) {
  (globalThis as unknown as { window: { pywebview: { api: Api } } }).window.pywebview = { api };
}

beforeEach(() => {
  vi.resetModules();
  (globalThis as unknown as { window: unknown }).window = {
    addEventListener: () => {},
  };
});

afterEach(() => {
  delete (globalThis as unknown as { window?: unknown }).window;
});

describe('invoke', () => {
  it('turns structured backend errors into BridgeCommandError', async () => {
    installApi({
      cmd_x: async () => ({ __error: true, code: 'VAULT_WRONG_PASSWORD', message: 'Incorrect password', detail: 'd' }),
    });
    const { invoke, BridgeCommandError } = await import('../lib/platform/core');
    const err = await invoke('cmd_x').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BridgeCommandError);
    expect((err as InstanceType<typeof BridgeCommandError>).code).toBe('VAULT_WRONG_PASSWORD');
    // The UI renders errors with String(e) — it must be the plain message.
    expect(String(err)).toBe('Incorrect password');
  });

  it('returns successful results unchanged', async () => {
    installApi({ cmd_ok: async () => ({ files: [] }) });
    const { invoke } = await import('../lib/platform/core');
    await expect(invoke('cmd_ok')).resolves.toEqual({ files: [] });
  });
});

describe('fetchFiles', () => {
  it('uses the backend cursor and forwards pagination args', async () => {
    const calls: unknown[] = [];
    installApi({
      cmd_get_files: async (args) => {
        calls.push(args);
        return { files: [{ id: 9, name: 'a.txt', size: 1 }], next_offset_id: 7 };
      },
    });
    const { fetchFiles } = await import('../lib/api');
    const page = await fetchFiles(42, 100);
    expect(calls).toEqual([{ folderId: 42, offsetId: 100, limit: 100 }]);
    // Even though the page holds 1 file, there are more messages to scan.
    expect(page.nextOffsetId).toBe(7);
    expect(page.files[0].sizeStr).toBeTruthy();
  });

  it('stops when the backend reports no more messages', async () => {
    installApi({ cmd_get_files: async () => ({ files: [], next_offset_id: 0 }) });
    const { fetchFiles } = await import('../lib/api');
    expect((await fetchFiles(null)).nextOffsetId).toBeUndefined();
  });
});

describe('folderOf / fileKey', () => {
  it('prefers the file’s own folder over the open one', async () => {
    const { folderOf, fileKey } = await import('../lib/api');
    expect(folderOf({ folder_id: 5 }, 9)).toBe(5);
    expect(folderOf({ folder_id: null }, 9)).toBeNull();
    expect(folderOf({}, 9)).toBe(9);
    expect(folderOf({}, undefined)).toBeNull();
    expect(fileKey({ id: 1, folder_id: 5 }, 9)).not.toBe(fileKey({ id: 1 }, 9));
  });
});
