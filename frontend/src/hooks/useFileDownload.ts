import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '../lib/platform/core';
import { save, open } from '../lib/platform/dialog';
import { listen, type UnlistenFn } from '../lib/platform/event';
import { toast } from 'sonner';
import { DownloadItem, TelegramFile } from '../types';
import { useSettings } from '../contexts/SettingsContext';
import type { Store } from '../lib/platform/store';

interface ProgressPayload {
  id: string;
  percent: number;
  uploaded_bytes: number;
  total_bytes: number;
  speed_bytes_per_sec: number;
}

export function useFileDownload(store: Store | null) {
  const { settings } = useSettings();
  const [downloadQueue, setDownloadQueue] = useState<DownloadItem[]>([]);
  const [initialized, setInitialized] = useState(false);
  const cancelledRef = useRef<Set<string>>(new Set());
  const activeCountRef = useRef(0);

  // Listen for progress events
  useEffect(() => {
    let unlisten: UnlistenFn | undefined;
    listen<ProgressPayload>('download-progress', (event) => {
      setDownloadQueue((q) =>
        q.map((i) =>
          i.id === event.payload.id
            ? {
                ...i,
                progress: event.payload.percent,
                uploadedBytes: event.payload.uploaded_bytes,
                totalBytes: event.payload.total_bytes,
                speedBytesPerSec: event.payload.speed_bytes_per_sec,
              }
            : i
        )
      );
    }).then((fn) => {
      unlisten = fn;
    });
    return () => {
      unlisten?.();
    };
  }, []);

  // Load saved queue on mount
  useEffect(() => {
    if (!store || initialized) return;
    store.get<DownloadItem[]>('downloadQueue').then((saved) => {
      if (saved && saved.length > 0) {
        const resumable = saved.filter((i) => i.status === 'pending' || i.status === 'paused');
        if (resumable.length > 0) {
          setDownloadQueue(resumable);
          toast.info(`Restored ${resumable.length} pending downloads`);
        }
      }
      setInitialized(true);
    });
  }, [store, initialized]);

  // Save queue when it changes (pending + paused items)
  useEffect(() => {
    if (!store || !initialized) return;
    const persistable = downloadQueue.filter((i) => i.status === 'pending' || i.status === 'paused');
    store.set('downloadQueue', persistable).then(() => store.save());
  }, [store, downloadQueue, initialized]);

  const processItem = useCallback(async (item: DownloadItem) => {
    activeCountRef.current++;
    setDownloadQueue((q) =>
      q.map((i) => (i.id === item.id ? { ...i, status: 'downloading', progress: 0 } : i))
    );

    try {
      // If item has a dirPath (bulk download), use it directly; otherwise prompt save dialog
      let savePath: string | null;
      if (item.dirPath) {
        // Sanitize filename to prevent path traversal
        const safeName = item.filename.replace(/[/\\]/g, '_').replace(/\.\./g, '_');
        savePath = `${item.dirPath}/${safeName}`;
      } else {
        savePath = await save({ defaultPath: item.filename });
      }

      if (!savePath) {
        setDownloadQueue((q) => q.filter((i) => i.id !== item.id));
        activeCountRef.current--;
        return;
      }

      await invoke('cmd_download_file', {
        messageId: item.messageId,
        savePath,
        folderId: item.folderId,
        transferId: item.id,
      });

      if (cancelledRef.current.has(item.id)) {
        cancelledRef.current.delete(item.id);
      } else {
        setDownloadQueue((q) =>
          q.map((i) => (i.id === item.id ? { ...i, status: 'success', progress: 100 } : i))
        );
        toast.success(`Downloaded: ${item.filename}`);
      }
    } catch (e) {
      if (!cancelledRef.current.has(item.id)) {
        const errMsg = String(e);
        if (errMsg.includes('Transfer cancelled')) {
          setDownloadQueue((q) =>
            q.map((i) => (i.id === item.id ? { ...i, status: 'cancelled' } : i))
          );
        } else {
          setDownloadQueue((q) =>
            q.map((i) => (i.id === item.id ? { ...i, status: 'error', error: errMsg } : i))
          );
          toast.error(`Download failed: ${item.filename}`);
        }
      } else {
        cancelledRef.current.delete(item.id);
      }
    } finally {
      activeCountRef.current--;
    }
  }, []);

  // Queue processor: launch up to maxConcurrentDownloads workers
  useEffect(() => {
    const max = settings.maxConcurrentDownloads;
    const pending = downloadQueue.filter((i) => i.status === 'pending');
    const slotsAvailable = max - activeCountRef.current;
    const toStart = pending.slice(0, slotsAvailable);
    for (const item of toStart) {
      setDownloadQueue((q) =>
        q.map((i) => (i.id === item.id ? { ...i, status: 'downloading' } : i))
      );
      processItem(item);
    }
  }, [downloadQueue, settings.maxConcurrentDownloads, processItem]);

  const queueDownload = (messageId: number, filename: string, folderId: number | null) => {
    const newItem: DownloadItem = {
      id: crypto.randomUUID(),
      messageId,
      filename,
      folderId,
      status: 'pending',
    };
    setDownloadQueue((prev) => [...prev, newItem]);
  };

  const queueBulkDownload = async (files: TelegramFile[], folderId: number | null) => {
    const dirPath = await open({
      directory: true,
      multiple: false,
      title: 'Select Download Destination',
    });
    if (!dirPath) return;

    const newItems: DownloadItem[] = files.map((file) => ({
      id: crypto.randomUUID(),
      messageId: file.id,
      filename: file.name,
      folderId,
      dirPath: dirPath as string,
      status: 'pending',
    }));
    setDownloadQueue((prev) => [...prev, ...newItems]);
    toast.info(`Queued ${files.length} files for download`);
  };

  const clearFinished = () => {
    setDownloadQueue((q) => q.filter((i) => i.status !== 'success'));
  };

  const cancelAll = () => {
    setDownloadQueue((q) => {
      const downloading = q.filter((i) => i.status === 'downloading');
      for (const item of downloading) {
        cancelledRef.current.add(item.id);
        invoke('cmd_cancel_transfer', { transferId: item.id }).catch(() => {});
      }
      return q
        .filter((i) => i.status !== 'pending')
        .map((i) => (i.status === 'downloading' ? { ...i, status: 'cancelled' as const } : i));
    });
    toast.info('All downloads cancelled');
  };

  const cancelItem = (id: string) => {
    setDownloadQueue((q) => {
      const item = q.find((i) => i.id === id);
      if (item?.status === 'downloading') {
        cancelledRef.current.add(id);
        invoke('cmd_cancel_transfer', { transferId: id }).catch(() => {});
        return q.map((i) => (i.id === id ? { ...i, status: 'cancelled' as const } : i));
      }
      if (item?.status === 'pending') {
        return q.filter((i) => i.id !== id);
      }
      return q;
    });
  };

  const retryItem = (id: string) => {
    setDownloadQueue((q) =>
      q.map((i) =>
        i.id === id && (i.status === 'error' || i.status === 'cancelled')
          ? {
              ...i,
              status: 'pending' as const,
              error: undefined,
              progress: undefined,
              uploadedBytes: undefined,
              totalBytes: undefined,
              speedBytesPerSec: undefined,
            }
          : i
      )
    );
  };

  const pauseItem = (id: string) => {
    setDownloadQueue((q) => {
      const item = q.find((i) => i.id === id);
      if (item?.status === 'downloading') {
        cancelledRef.current.add(id);
        invoke('cmd_cancel_transfer', { transferId: id }).catch(() => {});
        return q.map((i) =>
          i.id === id
            ? { ...i, status: 'paused' as const, resumeOffset: i.uploadedBytes || 0 }
            : i
        );
      }
      if (item?.status === 'pending') {
        return q.map((i) => (i.id === id ? { ...i, status: 'paused' as const } : i));
      }
      return q;
    });
  };

  const resumeItem = (id: string) => {
    setDownloadQueue((q) =>
      q.map((i) =>
        i.id === id && i.status === 'paused'
          ? { ...i, status: 'pending' as const, error: undefined }
          : i
      )
    );
  };

  return {
    downloadQueue,
    queueDownload,
    queueBulkDownload,
    clearFinished,
    cancelAll,
    cancelItem,
    retryItem,
    pauseItem,
    resumeItem,
  };
}
