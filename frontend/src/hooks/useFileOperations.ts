import { invoke, errorMessage } from '../lib/platform/core';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useConfirm } from '../contexts/ConfirmContext';
import { useSettings } from '../contexts/SettingsContext';
import { folderOf } from '../lib/api';
import { save } from '../lib/platform/dialog';
import { TelegramFile } from '../types';

export function useFileOperations(
  activeFolderId: number | null,
  selectedIds: number[],
  setSelectedIds: (ids: number[]) => void,
  displayedFiles: TelegramFile[],
  queueBulkDownload?: (files: TelegramFile[], folderId: number | null) => Promise<void>
) {
  const queryClient = useQueryClient();
  const { confirm } = useConfirm();
  const { settings } = useSettings();

  /** Folder of a displayed file (search results may live in other folders). */
  const folderFor = (id: number): number | null => {
    const file = displayedFiles.find((f) => f.id === id);
    return file ? folderOf(file, activeFolderId) : activeFolderId;
  };

  /** Group selected ids by the folder their file lives in. */
  const groupByFolder = (ids: number[]): Map<number | null, number[]> => {
    const groups = new Map<number | null, number[]>();
    for (const id of ids) {
      const folder = folderFor(id);
      groups.set(folder, [...(groups.get(folder) ?? []), id]);
    }
    return groups;
  };

  const confirmDelete = async (title: string, message: string, confirmText: string) =>
    !settings.confirmBeforeDelete ||
    confirm({ title, message, confirmText, variant: 'danger' });

  const handleDelete = async (id: number) => {
    if (!(await confirmDelete('Delete File', 'Are you sure you want to delete this file?', 'Delete'))) return;
    const folderId = folderFor(id);
    try {
      await invoke('cmd_delete_file', { messageId: id, folderId });
      queryClient.invalidateQueries({ queryKey: ['files', folderId] });
      toast.success('File deleted');
    } catch (e) {
      toast.error(`Delete failed: ${errorMessage(e)}`, { duration: 4000 });
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (
      !(await confirmDelete(
        'Delete Files',
        `Are you sure you want to delete ${selectedIds.length} files?`,
        'Delete All'
      ))
    )
      return;

    let success = 0;
    let fail = 0;
    for (const [folderId, ids] of groupByFolder(selectedIds)) {
      for (const id of ids) {
        try {
          await invoke('cmd_delete_file', { messageId: id, folderId });
          success++;
        } catch {
          fail++;
        }
      }
      queryClient.invalidateQueries({ queryKey: ['files', folderId] });
    }
    setSelectedIds([]);
    if (success > 0) toast.success(`Deleted ${success} files.`);
    if (fail > 0) toast.error(`Failed to delete ${fail} files.`, { duration: 4000 });
  };

  const handleDownload = async (id: number, name: string) => {
    try {
      const savePath = await save({ defaultPath: name });
      if (!savePath) return;
      toast.info(`Download started: ${name}`);
      await invoke('cmd_download_file', { messageId: id, savePath, folderId: folderFor(id) });
      toast.success(`Download complete: ${name}`);
    } catch (e) {
      toast.error(`Download failed: ${errorMessage(e)}`, { duration: 4000 });
    }
  };

  const handleBulkDownload = async () => {
    if (selectedIds.length === 0) return;
    if (queueBulkDownload) {
      for (const [folderId, ids] of groupByFolder(selectedIds)) {
        await queueBulkDownload(displayedFiles.filter((f) => ids.includes(f.id)), folderId);
      }
      setSelectedIds([]);
    }
  };

  const handleBulkMove = async (targetFolderId: number | null, onSuccess?: () => void) => {
    if (selectedIds.length === 0) return;
    try {
      for (const [sourceFolderId, ids] of groupByFolder(selectedIds)) {
        if (sourceFolderId === targetFolderId) continue;
        await invoke('cmd_move_files', { messageIds: ids, sourceFolderId, targetFolderId });
        queryClient.invalidateQueries({ queryKey: ['files', sourceFolderId] });
      }
      queryClient.invalidateQueries({ queryKey: ['files', targetFolderId] });
      toast.success(`Moved ${selectedIds.length} files.`);
      setSelectedIds([]);
      if (onSuccess) onSuccess();
    } catch (e) {
      toast.error(`Failed to move files: ${errorMessage(e)}`, { duration: 5000 });
    }
  };

  const handleDownloadFolder = async () => {
    if (displayedFiles.length === 0) {
      toast.info('Folder is empty.');
      return;
    }
    if (queueBulkDownload) {
      await queueBulkDownload(displayedFiles, activeFolderId);
    }
  };

  return {
    handleDelete,
    handleBulkDelete,
    handleDownload,
    handleBulkDownload,
    handleBulkMove,
    handleDownloadFolder,
    folderFor,
  };
}
