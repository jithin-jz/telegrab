import { useState, useEffect } from 'react';
import { invoke } from '../lib/platform/core';
import { load as loadStore, type Store } from '../lib/platform/store';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useConfirm } from '../contexts/ConfirmContext';
import { TelegramFolder } from '../types';
import { useNetworkStatus } from './useNetworkStatus';

export function useTelegramConnection(onLogoutParent: () => void) {
  const queryClient = useQueryClient();
  const { confirm } = useConfirm();

  const [folders, setFolders] = useState<TelegramFolder[]>([]);
  const [activeFolderId, setActiveFolderId] = useState<number | null>(null);
  const [store, setStore] = useState<Store | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isConnected, setIsConnected] = useState(true);

  const networkIsOnline = useNetworkStatus();

  // Load persisted store and restore saved folders.
  // NOTE: The Telegram connection is already established by App.tsx before
  // Dashboard mounts, so we do NOT call cmd_connect here. This prevents
  // duplicate network runners and race conditions in the Rust backend.
  useEffect(() => {
    const initStore = async () => {
      try {
        let _store = await loadStore('config.json');
        const checkId = await _store.get<string>('api_id');
        if (!checkId) {
          _store = await loadStore('settings.json');
        }
        setStore(_store);

        const savedFolders = await _store.get<TelegramFolder[]>('folders');
        if (savedFolders) setFolders(savedFolders);

        const savedActiveFolderId = await _store.get<number | null>('activeFolderId');
        if (savedActiveFolderId !== undefined) setActiveFolderId(savedActiveFolderId);

        // Connection is already live — just mark connected and refresh files
        setIsConnected(true);
        queryClient.invalidateQueries({ queryKey: ['files'] });
      } catch {
        // store not available
      }
    };
    initStore();
  }, [queryClient]);

  useEffect(() => {
    setIsConnected(networkIsOnline);
  }, [networkIsOnline]);

  const isNetworkError = (error: string): boolean => {
    const keywords = [
      'timeout',
      'connection',
      'network',
      'socket',
      'disconnected',
      'EOF',
      'ECONNREFUSED',
      'overflow',
    ];
    return keywords.some((k) => error.toLowerCase().includes(k.toLowerCase()));
  };

  const forceLogout = async () => {
    setIsConnected(false);
    try {
      await invoke('cmd_clean_cache').catch(() => {});
      if (store) {
        await store.delete('api_id');
        await store.delete('api_hash');
        await store.delete('folders');
        await store.save();
      }
    } catch {
      // best effort cleanup
    }
    toast.error('Connection lost. Please log in again.');
    onLogoutParent();
  };

  const handleLogout = async () => {
    if (
      !(await confirm({
        title: 'Sign Out',
        message: 'Are you sure you want to sign out? This will disconnect your active session.',
        confirmText: 'Sign Out',
        variant: 'danger',
      }))
    )
      return;

    try {
      await invoke('cmd_logout');
      await invoke('cmd_clean_cache');
      if (store) {
        await store.delete('api_id');
        await store.delete('api_hash');
        await store.delete('folders');
        await store.save();
      }
      onLogoutParent();
    } catch {
      toast.error('Error signing out');
      onLogoutParent();
    }
  };

  const handleSyncFolders = async () => {
    if (!store) return;
    setIsSyncing(true);
    try {
      const foundFolders = await invoke<TelegramFolder[]>('cmd_scan_folders');
      const foundIds = new Set(foundFolders.map((f) => f.id));

      // Remove folders that no longer exist on Telegram
      const removed = folders.filter((f) => !foundIds.has(f.id)).length;

      // Add new folders not yet in local list
      const existingIds = new Set(folders.map((f) => f.id));
      let added = 0;
      const merged = folders.filter((f) => foundIds.has(f.id));
      for (const f of foundFolders) {
        if (!existingIds.has(f.id)) {
          merged.push(f);
          added++;
        }
      }

      setFolders(merged);
      await store.set('folders', merged);
      await store.save();

      if (added > 0 || removed > 0) {
        const parts: string[] = [];
        if (added > 0) parts.push(`${added} added`);
        if (removed > 0) parts.push(`${removed} removed`);
        toast.success(`Sync complete. ${parts.join(', ')}.`);
      } else {
        toast.info('Scan complete. No changes.');
      }
    } catch {
      toast.error('Sync failed');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleCreateFolder = async (name: string) => {
    if (!store) return;
    try {
      const newFolder = await invoke<TelegramFolder>('cmd_create_folder', { name });
      const updated = [...folders, newFolder];
      setFolders(updated);
      await store.set('folders', updated);
      await store.save();
      toast.success(`Folder "${name}" created.`);
    } catch (e) {
      toast.error('Failed to create folder: ' + e);
      throw e;
    }
  };

  const handleRenameFolder = async (folderId: number, newName: string) => {
    const trimmed = newName.trim();
    if (!trimmed) return;

    const existing = folders.find((f) => f.id === folderId);
    if (!existing || existing.name === trimmed) return;

    // Optimistic update
    const previous = folders;
    const optimistic = folders.map((f) =>
      f.id === folderId ? { ...f, name: trimmed } : f
    );
    setFolders(optimistic);

    try {
      await invoke<TelegramFolder>('cmd_rename_folder', {
        folderId,
        name: trimmed,
      });
      if (store) {
        await store.set('folders', optimistic);
        await store.save();
      }
      toast.success(`Renamed to "${trimmed}".`);
    } catch (e) {
      setFolders(previous);
      toast.error('Failed to rename folder: ' + e);
      throw e;
    }
  };

  const handleFolderDelete = async (folderId: number, folderName: string) => {
    if (
      !(await confirm({
        title: 'Delete Folder',
        message: `Are you sure you want to delete "${folderName}"?\nThis will delete the channel on Telegram.`,
        confirmText: 'Delete',
        variant: 'danger',
      }))
    )
      return;

    try {
      await invoke('cmd_delete_folder', { folderId });
      const updated = folders.filter((f) => f.id !== folderId);
      setFolders(updated);
      if (store) {
        await store.set('folders', updated);
        await store.save();
      }
      if (activeFolderId === folderId) setActiveFolderId(null);
      toast.success(`Folder "${folderName}" deleted.`);
    } catch (e: unknown) {
      const errStr = String(e);
      if (errStr.includes('not found')) {
        if (
          await confirm({
            title: 'Folder Not Found',
            message: `Folder "${folderName}" not found on Telegram (it may have been deleted externally).\nRemove from this app?`,
            confirmText: 'Remove',
            variant: 'info',
          })
        ) {
          const updated = folders.filter((f) => f.id !== folderId);
          setFolders(updated);
          if (store) {
            await store.set('folders', updated);
            await store.save();
          }
          if (activeFolderId === folderId) setActiveFolderId(null);
        }
      } else {
        toast.error(`Failed to delete folder: ${e}`);
      }
    }
  };

  const handleSetActiveFolderId = async (id: number | null) => {
    setActiveFolderId(id);
    if (store) {
      await store.set('activeFolderId', id);
      await store.save();
    }
  };

  return {
    store,
    folders,
    activeFolderId,
    setActiveFolderId: handleSetActiveFolderId,
    isSyncing,
    isConnected,
    handleLogout,
    handleSyncFolders,
    handleCreateFolder,
    handleRenameFolder,
    handleFolderDelete,
    isNetworkError,
    forceLogout,
  };
}
