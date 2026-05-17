import { useMemo } from 'react';
import { HardDrive } from 'lucide-react';
import { motion } from 'framer-motion';
import { TelegramFile } from '../../types';
import { formatBytes } from '../../lib/utils';

interface StorageWidgetProps {
  files: TelegramFile[];
}

export function StorageWidget({ files }: StorageWidgetProps) {
  const totalSize = useMemo(() => files.reduce((sum, f) => sum + (f.size || 0), 0), [files]);

  if (files.length === 0) return null;

  // Visual segments by file type
  const categories = useMemo(() => {
    const media = files.filter((f) => /\.(mp4|mkv|avi|mov|mp3|flac|wav)$/i.test(f.name));
    const images = files.filter((f) => /\.(jpg|jpeg|png|gif|webp|svg|bmp)$/i.test(f.name));
    const docs = files.filter((f) => /\.(pdf|doc|docx|xls|xlsx|ppt|txt|zip|rar)$/i.test(f.name));
    const other = files.filter(
      (f) =>
        !media.includes(f) && !images.includes(f) && !docs.includes(f)
    );
    return [
      { label: 'Media', size: media.reduce((s, f) => s + (f.size || 0), 0), color: 'bg-violet-500' },
      { label: 'Images', size: images.reduce((s, f) => s + (f.size || 0), 0), color: 'bg-blue-500' },
      { label: 'Docs', size: docs.reduce((s, f) => s + (f.size || 0), 0), color: 'bg-emerald-500' },
      { label: 'Other', size: other.reduce((s, f) => s + (f.size || 0), 0), color: 'bg-slate-500' },
    ].filter((c) => c.size > 0);
  }, [files]);

  return (
    <div className="border-hairline bg-surface/50 mx-4 mb-3 rounded-lg border p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-slate flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide">
          <HardDrive className="h-3 w-3" />
          Storage
        </div>
        <span className="text-foreground text-xs font-semibold">{formatBytes(totalSize)}</span>
      </div>

      {/* Bar */}
      <div className="mb-2 flex h-2 w-full overflow-hidden rounded-full bg-white/[0.04]">
        {categories.map((cat) => (
          <motion.div
            key={cat.label}
            initial={{ width: 0 }}
            animate={{ width: `${(cat.size / totalSize) * 100}%` }}
            transition={{ duration: 0.8, ease: 'circOut' }}
            className={`${cat.color} h-full`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {categories.map((cat) => (
          <div key={cat.label} className="flex items-center gap-1">
            <div className={`${cat.color} h-2 w-2 rounded-full`} />
            <span className="text-slate text-[10px]">
              {cat.label} ({formatBytes(cat.size)})
            </span>
          </div>
        ))}
      </div>

      <div className="text-slate mt-1.5 text-[10px]">{files.length} files</div>
    </div>
  );
}
