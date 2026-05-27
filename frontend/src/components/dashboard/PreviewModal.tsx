import { useState, useEffect, useRef } from 'react';
import { X, File, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { invoke, convertFileSrc } from '../../lib/platform/core';
import { TelegramFile } from '../../types';
import { isImageFile, formatBytes } from '../../lib/utils';

const PREVIEW_CACHE_TTL_MS = 5 * 60 * 1000;
const PREVIEW_CACHE_MAX_ITEMS = 8;

type PreviewCacheValue = {
  src: string;
  cachedAt: number;
};

const previewCache = new Map<string, PreviewCacheValue>();
const pendingPrefetch = new Set<string>();

const getPreviewCacheKey = (fileId: number, folderId: number | null) =>
  `${folderId ?? 'home'}:${fileId}`;

const touchPreviewCache = (key: string, value: PreviewCacheValue) => {
  if (previewCache.has(key)) previewCache.delete(key);
  previewCache.set(key, value);

  while (previewCache.size > PREVIEW_CACHE_MAX_ITEMS) {
    const oldestKey = previewCache.keys().next().value;
    if (!oldestKey) break;
    previewCache.delete(oldestKey);
  }
};

const getCachedPreview = (key: string): string | null => {
  const value = previewCache.get(key);
  if (!value) return null;

  if (Date.now() - value.cachedAt > PREVIEW_CACHE_TTL_MS) {
    previewCache.delete(key);
    return null;
  }

  touchPreviewCache(key, value);
  return value.src;
};

const rememberPreview = (key: string, src: string) => {
  touchPreviewCache(key, { src, cachedAt: Date.now() });
};

const forgetPreview = (key: string) => {
  previewCache.delete(key);
};

const isSafeToPrefetch = (name: string) => isImageFile(name);

interface PreviewModalProps {
  file: TelegramFile;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  onDownload?: (file: TelegramFile) => void;
  currentIndex?: number;
  totalItems?: number;
  nextFile?: TelegramFile | null;
  prevFile?: TelegramFile | null;
  activeFolderId: number | null;
}

export function PreviewModal({
  file,
  onClose,
  onNext,
  onPrev,
  onDownload,
  currentIndex,
  totalItems,
  nextFile,
  prevFile,
  activeFolderId,
}: PreviewModalProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const latestRequestRef = useRef(0);

  useEffect(() => {
    setRetryCount(0);
    setReloadNonce(0);
  }, [file.id, activeFolderId]);

  useEffect(() => {
    const load = async () => {
      const key = getPreviewCacheKey(file.id, activeFolderId);
      const shouldBypassCache = reloadNonce > 0;
      const requestId = ++latestRequestRef.current;
      const cachedSrc = shouldBypassCache ? null : getCachedPreview(key);

      if (cachedSrc) {
        if (requestId !== latestRequestRef.current) return;
        setSrc(cachedSrc);
        setLoading(false);
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const path = await invoke<string>('cmd_get_preview', {
          messageId: file.id,
          folderId: activeFolderId,
        });
        if (requestId !== latestRequestRef.current) return;

        if (path) {
          if (path.startsWith('data:')) {
            setSrc(path);
            rememberPreview(key, path);
          } else {
            const converted = convertFileSrc(path);
            setSrc(converted);
            rememberPreview(key, converted);
          }
        } else {
          setError('Preview not available');
        }
      } catch (e) {
        if (requestId !== latestRequestRef.current) return;
        setError(String(e));
      } finally {
        if (requestId !== latestRequestRef.current) return;
        setLoading(false);
      }
    };
    load();
  }, [file, activeFolderId, reloadNonce]);

  useEffect(() => {
    const candidates = [nextFile, prevFile].filter(
      (f): f is TelegramFile => !!f && isSafeToPrefetch(f.name)
    );

    candidates.forEach((candidate) => {
      const key = getPreviewCacheKey(candidate.id, activeFolderId);
      if (getCachedPreview(key) || pendingPrefetch.has(key)) return;

      pendingPrefetch.add(key);
      invoke<string>('cmd_get_preview', {
        messageId: candidate.id,
        folderId: activeFolderId,
      })
        .then((path) => {
          if (!path) return;
          const normalized = path.startsWith('data:') ? path : convertFileSrc(path);
          rememberPreview(key, normalized);
        })
        .catch(() => {
          // Ignore prefetch errors, main preview flow will handle user-visible failures.
        })
        .finally(() => {
          pendingPrefetch.delete(key);
        });
    });
  }, [nextFile, prevFile, activeFolderId]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return;
      }

      const key = e.key.toLowerCase();

      if (e.key === 'ArrowRight' || key === 'l') {
        e.preventDefault();
        onNext?.();
        return;
      }

      if (e.key === 'ArrowLeft' || key === 'j') {
        e.preventDefault();
        onPrev?.();
        return;
      }

      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, onNext, onPrev]);

  return (
    <div
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/90 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-screen w-full max-w-5xl flex-col items-center justify-center"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onPrev}
          className="absolute top-1/2 left-2 -translate-y-1/2 rounded-full bg-black/60 p-2 transition-colors hover:bg-black/80"
          style={{ color: '#ffffff' }}
          title="Previous (ArrowLeft / J)"
        >
          <ChevronLeft className="h-6 w-6" />
        </button>

        <button
          onClick={onNext}
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full bg-black/60 p-2 transition-colors hover:bg-black/80"
          style={{ color: '#ffffff' }}
          title="Next (ArrowRight / L)"
        >
          <ChevronRight className="h-6 w-6" />
        </button>

        <button
          onClick={onClose}
          className="absolute -top-12 right-0 rounded-full bg-black/60 p-2 transition-colors hover:bg-black/80"
          style={{ color: '#ffffff' }}
        >
          <X className="h-6 w-6" />
        </button>

        {loading && (
          <div className="flex flex-col items-center gap-4 text-white">
            <div className="border-primary h-10 w-10 animate-spin rounded-full border-4 border-t-transparent"></div>
            <p>Loading preview...</p>
            <p className="text-xs text-white/50">Downloading from Telegram...</p>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center rounded-xl border border-white/10 bg-[#1c1c1c] p-8 text-center shadow-2xl">
            <File className="mb-4 h-14 w-14 text-gray-400" />
            <h3 className="mb-1 text-lg font-medium text-white">{file.name}</h3>
            <p className="mb-3 text-sm text-gray-500">{formatBytes(file.size)}</p>
            <p className="mb-6 max-w-xs text-xs text-red-400/80">{error}</p>
            {onDownload && (
              <button
                onClick={() => onDownload(file)}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
              >
                <Download className="h-4 w-4" />
                Download File
              </button>
            )}
          </div>
        )}

        {!loading && !error && src && (
          <div className="flex flex-col items-center">
            {isImageFile(file.name) ? (
              <img
                src={src}
                className="max-h-[85vh] max-w-full rounded-lg bg-black object-contain shadow-2xl"
                alt="Preview"
                onError={() => {
                  const key = getPreviewCacheKey(file.id, activeFolderId);
                  forgetPreview(key);

                  if (retryCount < 1) {
                    setRetryCount((prev) => prev + 1);
                    setReloadNonce((prev) => prev + 1);
                    return;
                  }

                  setError('Failed to render image preview');
                }}
              />
            ) : (
              <div className="rounded-xl border border-white/10 bg-[#1c1c1c] p-8 text-center shadow-2xl">
                <File className="text-primary mx-auto mb-4 h-16 w-16" />
                <h3 className="mb-2 text-xl font-medium text-white">{file.name}</h3>
                <p className="mb-2 text-sm text-gray-500">{formatBytes(file.size)}</p>
                <p className="mb-6 text-gray-400">Preview not supported in app.</p>
                <p className="text-xs text-gray-500">File type: {file.name.split('.').pop()}</p>
              </div>
            )}
          </div>
        )}

        <div className="absolute bottom-[-3rem] text-sm text-white opacity-50">
          {file.name}
          {typeof currentIndex === 'number' && typeof totalItems === 'number' && totalItems > 0 && (
            <span className="ml-3">
              {currentIndex + 1}/{totalItems}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
