import { DownloadItem } from '../../types';
import { Download, Check, X, AlertCircle, RotateCcw } from 'lucide-react';
import { getDownloadProgress, useDownloadProgressTick } from '../../hooks/useFileDownload';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

interface DownloadQueueProps {
  items: DownloadItem[];
  onClearFinished: () => void;
  onCancelAll: () => void;
  onCancelItem: (id: string) => void;
  onRetryItem: (id: string) => void;
}

export function DownloadQueue({
  items,
  onClearFinished,
  onCancelAll,
  onCancelItem,
  onRetryItem,
}: DownloadQueueProps) {
  useDownloadProgressTick(); // subscribe to progress updates

  if (items.length === 0) return null;

  const activeCount = items.filter(
    (i) => i.status === 'pending' || i.status === 'downloading'
  ).length;
  const completedCount = items.filter((i) => i.status === 'success').length;

  return (
    <div className="auth-glass border-hairline pointer-events-auto w-full overflow-hidden shadow-2xl">
      <div className="border-hairline flex items-center justify-between gap-3 border-b bg-white/[0.02] p-3">
        <div className="flex min-w-0 items-center gap-2">
          <Download className="text-link-blue h-4 w-4" />
          <h4 className="text-foreground truncate text-[13px] font-semibold">Downloads</h4>
          {activeCount > 0 && (
            <span className="bg-link-blue/20 text-link-blue shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-bold tracking-tight uppercase">
              {activeCount} active
            </span>
          )}
        </div>
        <div className="flex shrink-0 gap-2.5">
          {activeCount > 0 && (
            <button
              onClick={onCancelAll}
              className="text-[11px] font-medium text-rose-400/80 transition-colors hover:text-rose-400"
            >
              Cancel All
            </button>
          )}
          {completedCount > 0 && (
            <button
              onClick={onClearFinished}
              className="text-primary hover:text-primary-pressed text-[11px] font-medium transition-colors"
            >
              Clear Finished
            </button>
          )}
        </div>
      </div>
      <div className="custom-scrollbar smooth-scroll max-h-60 space-y-1.5 overflow-y-auto p-2">
        {items.map((item) => {
          const progress = item.status === 'downloading' ? getDownloadProgress(item.id) : undefined;
          return (
          <div
            key={item.id}
            className="border-hairline-soft flex flex-col gap-1 rounded-lg border bg-white/[0.03] p-2 transition-colors hover:bg-white/[0.05]"
          >
            <div className="flex items-center gap-3 text-[13px]">
              <div className="flex-shrink-0">
                {item.status === 'pending' && (
                  <div className="flex h-4 w-4 items-center justify-center rounded-full bg-amber-400/20">
                    <div className="h-2 w-2 rounded-full bg-amber-400" />
                  </div>
                )}
                {item.status === 'downloading' && (
                  <div className="border-link-blue h-4 w-4 animate-spin rounded-full border-2 border-t-transparent shadow-[0_0_6px_rgba(91,141,239,0.4)]" />
                )}
                {item.status === 'success' && (
                  <div className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20">
                    <Check className="h-3 w-3 text-emerald-500" />
                  </div>
                )}
                {item.status === 'error' && (
                  <div className="flex h-4 w-4 items-center justify-center rounded-full bg-rose-500/20">
                    <X className="h-3 w-3 text-rose-500" />
                  </div>
                )}
                {item.status === 'cancelled' && (
                  <div className="bg-stone/20 flex h-4 w-4 items-center justify-center rounded-full">
                    <X className="text-stone h-3 w-3" />
                  </div>
                )}
              </div>
              <div className="text-foreground/90 flex-1 truncate font-medium" title={item.filename}>
                {item.filename}
              </div>
              {item.status === 'downloading' && (
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
            {item.status === 'downloading' && (
              <>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/10 p-[0.5px]">
                  {progress ? (
                    <div
                      className="bg-link-blue h-full rounded-full transition-all duration-300"
                      style={{ width: `${progress.percent}%` }}
                    />
                  ) : (
                    <div className="bg-link-blue animate-progress-indeterminate h-full w-full" />
                  )}
                </div>
                <div className="text-telegram-subtext mt-0.5 flex justify-between text-[10px]">
                  <span>
                    {progress
                      ? `${formatBytes(progress.uploaded_bytes)} / ${formatBytes(progress.total_bytes)}`
                      : ''}
                  </span>
                  <span>
                    {progress && progress.speed_bytes_per_sec > 0
                      ? `${formatBytes(progress.speed_bytes_per_sec)}/s`
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
          );
        })}
      </div>
    </div>
  );
}
