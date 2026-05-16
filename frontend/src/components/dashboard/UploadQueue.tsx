import { QueueItem } from '../../types';
import { X, RotateCcw, AlertCircle } from 'lucide-react';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

interface UploadQueueProps {
  items: QueueItem[];
  onClearFinished: () => void;
  onCancelAll: () => void;
  onCancelItem: (id: string) => void;
  onRetryItem: (id: string) => void;
}

export function UploadQueue({
  items,
  onClearFinished,
  onCancelAll,
  onCancelItem,
  onRetryItem,
}: UploadQueueProps) {
  if (items.length === 0) return null;

  const hasPendingOrActive = items.some((i) => i.status === 'pending' || i.status === 'uploading');

  return (
    <div className="auth-glass border-hairline pointer-events-auto w-full overflow-hidden shadow-2xl">
      <div className="border-hairline flex items-center justify-between gap-3 border-b bg-white/[0.02] p-3">
        <h4 className="text-foreground text-[13px] font-semibold">Uploads</h4>
        <div className="flex gap-2.5">
          {hasPendingOrActive && (
            <button
              onClick={onCancelAll}
              className="text-[11px] font-medium text-rose-400/80 transition-colors hover:text-rose-400"
            >
              Cancel All
            </button>
          )}
          <button
            onClick={onClearFinished}
            className="text-primary hover:text-primary-pressed text-[11px] font-medium transition-colors"
          >
            Clear Finished
          </button>
        </div>
      </div>
      <div className="custom-scrollbar max-h-60 space-y-1.5 overflow-y-auto p-2">
        {items.map((item) => (
          <div
            key={item.id}
            className="border-hairline-soft flex flex-col gap-1 rounded-lg border bg-white/[0.03] p-2 transition-colors hover:bg-white/[0.05]"
          >
            <div className="flex items-center gap-3 text-[13px]">
              <div
                className={`h-2 w-2 flex-shrink-0 rounded-full shadow-sm ${
                  item.status === 'pending'
                    ? 'bg-amber-400'
                    : item.status === 'uploading'
                      ? 'bg-primary animate-pulse shadow-[0_0_6px_rgba(124,92,255,0.4)]'
                      : item.status === 'cancelled'
                        ? 'bg-stone'
                        : item.status === 'error'
                          ? 'bg-rose-500'
                          : 'bg-emerald-500'
                }`}
              />
              <div className="text-foreground/90 flex-1 truncate font-medium" title={item.path}>
                {item.path.split('/').pop()}
              </div>
              {item.status === 'uploading' && (
                <button
                  onClick={() => onCancelItem(item.id)}
                  className="flex-shrink-0 text-gray-400 transition-colors hover:text-red-400"
                  title="Cancel"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              {item.status === 'pending' && (
                <button
                  onClick={() => onCancelItem(item.id)}
                  className="flex-shrink-0 text-gray-400 transition-colors hover:text-red-400"
                  title="Remove"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              {(item.status === 'error' || item.status === 'cancelled') && (
                <button
                  onClick={() => onRetryItem(item.id)}
                  className="flex-shrink-0 text-gray-400 transition-colors hover:text-blue-400"
                  title="Retry"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            {item.status === 'uploading' && (
              <>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/10 p-[0.5px]">
                  {item.progress !== undefined ? (
                    <div
                      className="bg-primary h-full rounded-full transition-all duration-300"
                      style={{ width: `${item.progress}%` }}
                    />
                  ) : (
                    <div className="bg-primary animate-progress-indeterminate h-full w-full" />
                  )}
                </div>
                <div className="text-telegram-subtext mt-0.5 flex justify-between text-[10px]">
                  <span>
                    {item.uploadedBytes !== undefined && item.totalBytes !== undefined
                      ? `${formatBytes(item.uploadedBytes)} / ${formatBytes(item.totalBytes)}`
                      : item.progress !== undefined
                        ? `${item.progress}%`
                        : ''}
                  </span>
                  <span>
                    {item.speedBytesPerSec !== undefined && item.speedBytesPerSec > 0
                      ? `${formatBytes(item.speedBytesPerSec)}/s`
                      : ''}
                  </span>
                </div>
              </>
            )}
            {item.status === 'error' && item.error && (
              <div className="mt-1 flex items-center gap-1 text-xs text-red-400">
                <AlertCircle className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{item.error}</span>
              </div>
            )}
            {item.status === 'cancelled' && (
              <div className="mt-0.5 text-xs text-gray-400">Cancelled</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
