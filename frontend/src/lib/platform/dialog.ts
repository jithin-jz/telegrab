/**
 * Desktop platform file dialogs — open, save, confirm, message.
 */

import { callPy } from './internal';

interface DialogFilter {
  name: string;
  extensions: string[];
}

interface OpenDialogOptions {
  title?: string;
  defaultPath?: string;
  multiple?: boolean;
  directory?: boolean;
  filters?: DialogFilter[];
}

interface SaveDialogOptions {
  title?: string;
  defaultPath?: string;
  filters?: DialogFilter[];
}

export async function open(options: OpenDialogOptions = {}): Promise<string | string[] | null> {
  const result = await callPy<string | string[] | null>('cmd_dialog_open', {
    title: options.title ?? 'Open',
    directory: !!options.directory,
    multiple: !!options.multiple,
    filters: options.filters ?? [],
    defaultPath: options.defaultPath ?? null,
  });
  return result;
}

export async function save(options: SaveDialogOptions = {}): Promise<string | null> {
  const result = await callPy<string | null>('cmd_dialog_save', {
    title: options.title ?? 'Save',
    defaultPath: options.defaultPath ?? null,
    filters: options.filters ?? [],
  });
  return result;
}

/**
 * `confirm` and `message` aren't actually used by the React app
 * (they have an in-app `<ConfirmDialog>` component), but we re-export
 * them as no-op-friendly fallbacks just in case.
 */
export function confirm(message: string): Promise<boolean> {
  return Promise.resolve(window.confirm(message));
}

export function message(text: string): Promise<void> {
  window.alert(text);
  return Promise.resolve();
}

export function ask(text: string): Promise<boolean> {
  return Promise.resolve(window.confirm(text));
}
