import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '../lib/platform/core';
import { open } from '../lib/platform/dialog';
import { listen, type UnlistenFn } from '../lib/platform/event';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { QueueItem } from '../types';
import { useSettings } from '../contexts/SettingsContext';
import type { Store } from '../lib/platform/store';

interface ProgressPayload {
  id: string;
  percent: number;
  uploaded_bytes: number;
  total_bytes: number;
  speed_bytes_per_sec: number;
}

// External progress store — avoids re-rendering the entire tree on every tick
const uploadProgressMap = new Map<string, ProgressPayload>();
const uploadProgressListeners = new Set<() => void>();

export function getUploadProgress(id: string): ProgressPayload | undefined {
  return uploadProgressMap.get(id);
}

export function useUploadProgressTick(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const cb = () => setTick((t) => t + 1);
    uploadProgressListeners.add(cb);
    return () => { uploadProgressListeners.delete(cb); };
  }, []);
  return tick;
}

function notifyProgressListeners() {
  for (const cb of uploadProgressListeners) cb();
}

export function useFileUpload(activeFolderId: number | null, store: Store | null) {
  const queryClient = useQueryClient();
  const { settings } = useSettings();
  const [uploadQueue, setUploadQueue] = useState<QueueItem[]>([]);
  const [initialized, setInitialized] = useState(false);
  const cancelledRef = useRef<Set<string>>(new Set());
  const activeCountRef = useRef(0);

  // Listen for progress events — update external map, NOT queue state
  useEffect(() => {
    let unlisten: UnlistenFn | undefined;
    listen<ProgressPayload>('upload-progress', (event) => {
      uploadProgressMap.set(event.payload.id, event.payload);
      notifyProgressListeners();
    }).then((fn) => { unlisten = fn; });
    return () => { unlisten?.(); };
  }, []);

  useEffect(() => {
    if (!store || initialized) return;
    store.get<QueueItem[]>('uploadQueue').then((saved) => {
      if (saved && saved.length > 0) {
        const pending = saved.filter((i) => i.status === 'pending');
        if (pending.length > 0) {
          setUploadQueue(pending);
          toast.info(`Restored ${pending.length} pending uploads`);
        }
      }
      setInitialized(true);
    });
  }, [store, initialized]);

  useEffect(() => {
    if (!store || !initialized) return;
    const persistable = uploadQueue.filter((i) => i.status === 'pending' || i.status === 'paused');
    store.set('uploadQueue', persistable).then(() => store.save());
  }, [store, uploadQueue, initialized]);

  const processItem = useCallback(
    async (item: QueueItem) => {
      activeCountRef.current++;
      setUploadQueue((q) =>
        q.map((i) => (i.id === item.id ? { ...i, status: 'uploading', progress: 0 } : i))
      );
      try {
        if (!item.skipDuplicateCheck) {
          try {
            const dupResult = await invoke<{ duplicate: boolean; existing: any }>('cmd_check_duplicate', {
              path: item.path,
              folderId: item.folderId,
            });
            if (dupResult.duplicate && dupResult.existing) {
              setUploadQueue((q) =>
                q.map((i) =>
                  i.id === item.id
                    ? { ...i, status: 'error' as const, error: `Duplicate: "${dupResult.existing.name}" already exists` }
                    : i
                )
              );
              activeCountRef.current--;
              return;
            }
          } catch { /* proceed */ }
        }

        await invoke('cmd_upload_file', {
          path: item.path,
          folderId: item.folderId,
          transferId: item.id,
        });
        if (cancelledRef.current.has(item.id)) {
          cancelledRef.current.delete(item.id);
        } else {
          setUploadQueue((q) =>
            q.map((i) => (i.id === item.id ? { ...i, status: 'success', progress: 100 } : i))
          );
          queryClient.invalidateQueries({ queryKey: ['files', item.folderId] });
        }
      } catch (e) {
        if (!cancelledRef.current.has(item.id)) {
          const errMsg = String(e);
          if (errMsg.includes('Transfer cancelled')) {
            setUploadQueue((q) =>
              q.map((i) => (i.id === item.id ? { ...i, status: 'cancelled' } : i))
            );
          } else {
            setUploadQueue((q) =>
              q.map((i) => (i.id === item.id ? { ...i, status: 'error', error: errMsg } : i))
            );
            toast.error(`Upload failed: ${e}`);
          }
        } else {
          cancelledRef.current.delete(item.id);
        }
      } finally {
        activeCountRef.current--;
        uploadProgressMap.delete(item.id);
      }
    },
    [queryClient]
  );

  useEffect(() => {
    const max = settings.maxConcurrentUploads;
    const pending = uploadQueue.filter((i) => i.status === 'pending');
    const slotsAvailable = max - activeCountRef.current;
    const toStart = pending.slice(0, slotsAvailable);
    for (const item of toStart) {
      setUploadQueue((q) =>
        q.map((i) => (i.id === item.id ? { ...i, status: 'uploading' } : i))
      );
      processItem(item);
    }
  }, [uploadQueue, settings.maxConcurrentUploads, processItem]);

  const handleManualUpload = async () => {
    try {
      const selected = await open({ multiple: true, directory: false });
      if (selected) {
        const paths = Array.isArray(selected) ? selected : [selected];
        const newItems: QueueItem[] = paths.map((path: string) => ({
          id: crypto.randomUUID(),
          path,
          folderId: activeFolderId,
          status: 'pending',
        }));
        setUploadQueue((prev) => [...prev, ...newItems]);
        toast.info(`Queued ${paths.length} files for upload`);
      }
    } catch {
      toast.error('Failed to open file dialog');
    }
  };

  const cancelAll = () => {
    setUploadQueue((q) => {
      const uploading = q.filter((i) => i.status === 'uploading');
      for (const item of uploading) {
        cancelledRef.current.add(item.id);
        invoke('cmd_cancel_transfer', { transferId: item.id }).catch(() => {});
      }
      return q
        .filter((i) => i.status !== 'pending')
        .map((i) => (i.status === 'uploading' ? { ...i, status: 'cancelled' as const } : i));
    });
    toast.info('All uploads cancelled');
  };

  const cancelItem = (id: string) => {
    setUploadQueue((q) => {
      const item = q.find((i) => i.id === id);
      if (item?.status === 'uploading') {
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

  const retryItem = (id: string, skipDuplicateCheck?: boolean) => {
    setUploadQueue((q) =>
      q.map((i) =>
        i.id === id && (i.status === 'error' || i.status === 'cancelled')
          ? {
              ...i,
              status: 'pending' as const,
              error: undefined,
              progress: undefined,
              skipDuplicateCheck: skipDuplicateCheck ?? i.skipDuplicateCheck,
            }
          : i
      )
    );
  };

  const pauseItem = (id: string) => {
    setUploadQueue((q) => {
      const item = q.find((i) => i.id === id);
      if (item?.status === 'uploading') {
        cancelledRef.current.add(id);
        invoke('cmd_cancel_transfer', { transferId: id }).catch(() => {});
        return q.map((i) =>
          i.id === id ? { ...i, status: 'paused' as const } : i
        );
      }
      if (item?.status === 'pending') {
        return q.map((i) => (i.id === id ? { ...i, status: 'paused' as const } : i));
      }
      return q;
    });
  };

  const resumeItem = (id: string) => {
    setUploadQueue((q) =>
      q.map((i) =>
        i.id === id && i.status === 'paused'
          ? { ...i, status: 'pending' as const, error: undefined }
          : i
      )
    );
  };

  return {
    uploadQueue,
    setUploadQueue,
    handleManualUpload,
    cancelAll,
    cancelItem,
    retryItem,
    pauseItem,
    resumeItem,
  };
}
