import { DownloadItem } from "../../types";
import { Download, Check, X, AlertCircle, RotateCcw } from "lucide-react";

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

export function DownloadQueue({ items, onClearFinished, onCancelAll, onCancelItem, onRetryItem }: DownloadQueueProps) {
    if (items.length === 0) return null;

    const activeCount = items.filter(i => i.status === 'pending' || i.status === 'downloading').length;
    const completedCount = items.filter(i => i.status === 'success').length;

    return (
        <div className="w-full auth-glass border-hairline overflow-hidden shadow-2xl pointer-events-auto">
            <div className="p-3 border-b border-hairline bg-white/[0.02] flex justify-between items-center gap-3">
                <div className="flex items-center gap-2 min-w-0">
                    <Download className="w-4 h-4 text-link-blue" />
                    <h4 className="text-[13px] font-semibold text-foreground truncate">Downloads</h4>
                    {activeCount > 0 && (
                        <span className="text-[10px] font-bold px-1.5 py-0.5 bg-link-blue/20 text-link-blue rounded-full shrink-0 uppercase tracking-tight">
                            {activeCount} active
                        </span>
                    )}
                </div>
                <div className="flex gap-2.5 shrink-0">
                    {activeCount > 0 && (
                        <button onClick={onCancelAll} className="text-[11px] font-medium text-rose-400/80 hover:text-rose-400 transition-colors">Cancel All</button>
                    )}
                    {completedCount > 0 && (
                        <button onClick={onClearFinished} className="text-[11px] font-medium text-primary hover:text-primary-pressed transition-colors">
                            Clear Finished
                        </button>
                    )}
                </div>
            </div>
            <div className="max-h-60 overflow-y-auto p-2 space-y-1.5 custom-scrollbar">
                {items.map(item => (
                    <div key={item.id} className="flex flex-col gap-1 p-2 bg-white/[0.03] border border-hairline-soft rounded-lg transition-colors hover:bg-white/[0.05]">
                        <div className="flex items-center gap-3 text-[13px]">
                            <div className="flex-shrink-0">
                                {item.status === 'pending' && <div className="w-4 h-4 rounded-full bg-amber-400/20 flex items-center justify-center"><div className="w-2 h-2 bg-amber-400 rounded-full" /></div>}
                                {item.status === 'downloading' && <div className="w-4 h-4 rounded-full border-2 border-link-blue border-t-transparent animate-spin shadow-[0_0_6px_rgba(91,141,239,0.4)]" />}
                                {item.status === 'success' && <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center"><Check className="w-3 h-3 text-emerald-500" /></div>}
                                {item.status === 'error' && <div className="w-4 h-4 rounded-full bg-rose-500/20 flex items-center justify-center"><X className="w-3 h-3 text-rose-500" /></div>}
                                {item.status === 'cancelled' && <div className="w-4 h-4 rounded-full bg-stone/20 flex items-center justify-center"><X className="w-3 h-3 text-stone" /></div>}
                            </div>
                            <div className="flex-1 truncate text-foreground/90 font-medium" title={item.filename}>
                                {item.filename}
                            </div>
                            {item.status === 'downloading' && (
                                <button onClick={() => onCancelItem(item.id)} className="text-gray-400 hover:text-red-400 transition-colors flex-shrink-0" title="Cancel">
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            )}
                            {item.status === 'pending' && (
                                <button onClick={() => onCancelItem(item.id)} className="text-gray-400 hover:text-red-400 transition-colors flex-shrink-0" title="Remove">
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            )}
                            {(item.status === 'error' || item.status === 'cancelled') && (
                                <button onClick={() => onRetryItem(item.id)} className="text-gray-400 hover:text-blue-400 transition-colors flex-shrink-0" title="Retry">
                                    <RotateCcw className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </div>
                        {item.status === 'downloading' && (
                            <>
                                <div className="w-full bg-white/10 h-1.5 mt-1.5 rounded-full overflow-hidden p-[0.5px]">
                                    {item.progress !== undefined ? (
                                        <div
                                            className="bg-link-blue h-full rounded-full transition-all duration-300"
                                            style={{ width: `${item.progress}%` }}
                                        />
                                    ) : (
                                        <div className="bg-link-blue h-full w-full animate-progress-indeterminate" />
                                    )}
                                </div>
                                <div className="flex justify-between text-[10px] text-telegram-subtext mt-0.5">
                                    <span>
                                        {item.uploadedBytes !== undefined && item.totalBytes !== undefined
                                            ? `${formatBytes(item.uploadedBytes)} / ${formatBytes(item.totalBytes)}`
                                            : item.progress !== undefined ? `${item.progress}%` : ''}
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
                            <div className="flex items-center gap-1 text-xs text-red-400 mt-1">
                                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                                <span className="truncate">{item.error}</span>
                            </div>
                        )}
                        {item.status === 'cancelled' && <div className="text-xs text-gray-400 mt-0.5">Cancelled</div>}
                    </div>
                ))}
            </div>
        </div>
    )
}
