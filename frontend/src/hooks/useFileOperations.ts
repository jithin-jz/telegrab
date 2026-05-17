import { invoke } from '../lib/platform/core';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useConfirm } from '../contexts/ConfirmContext';
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

  const handleDelete = async (id: number) => {
    if (
      !(await confirm({
        title: 'Delete File',
        message: 'Are you sure you want to delete this file?',
        confirmText: 'Delete',
        variant: 'danger',
      }))
    )
      return;
    try {
      await invoke('cmd_delete_file', { messageId: id, folderId: activeFolderId });
      queryClient.invalidateQueries({ queryKey: ['files', activeFolderId] });
      toast.success('File deleted');
    } catch (e) {
      toast.error(`Delete failed: ${e}`);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (
      !(await confirm({
        title: 'Delete Files',
        message: `Are you sure you want to delete ${selectedIds.length} files?`,
        confirmText: 'Delete All',
        variant: 'danger',
      }))
    )
      return;

    let success = 0;
    let fail = 0;
    for (const id of selectedIds) {
      try {
        await invoke('cmd_delete_file', { messageId: id, folderId: activeFolderId });
        success++;
      } catch {
        fail++;
      }
    }
    setSelectedIds([]);
    queryClient.invalidateQueries({ queryKey: ['files', activeFolderId] });
    if (success > 0) toast.success(`Deleted ${success} files.`);
    if (fail > 0) toast.error(`Failed to delete ${fail} files.`);
  };

  const handleDownload = async (id: number, name: string) => {
    try {
      const savePath = await import('../lib/platform/dialog').then((d) =>
        d.save({ defaultPath: name })
      );
      if (!savePath) return;
      toast.info(`Download started: ${name}`);
      await invoke('cmd_download_file', { messageId: id, savePath, folderId: activeFolderId });
      toast.success(`Download complete: ${name}`);
    } catch (e) {
      toast.error(`Download failed: ${e}`);
    }
  };

  const handleBulkDownload = async () => {
    if (selectedIds.length === 0) return;
    const targetFiles = displayedFiles.filter((f) => selectedIds.includes(f.id));
    if (queueBulkDownload) {
      await queueBulkDownload(targetFiles, activeFolderId);
      setSelectedIds([]);
    }
  };

  const handleBulkMove = async (targetFolderId: number | null, onSuccess?: () => void) => {
    if (selectedIds.length === 0) return;
    try {
      await invoke('cmd_move_files', {
        messageIds: selectedIds,
        sourceFolderId: activeFolderId,
        targetFolderId: targetFolderId,
      });
      toast.success(`Moved ${selectedIds.length} files.`);
      queryClient.invalidateQueries({ queryKey: ['files', activeFolderId] });
      setSelectedIds([]);
      if (onSuccess) onSuccess();
    } catch {
      toast.error('Failed to move files');
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
    handleGlobalSearch: async (query: string) => {
      try {
        return await invoke<TelegramFile[]>('cmd_search_global', { query });
      } catch {
        return [];
      }
    },
  };
}
