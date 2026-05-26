import { BandwidthStats } from '../../types';
import { formatBytes } from '../../lib/utils';
import { motion } from 'framer-motion';
import { cn } from '../../lib/utils';

interface BandwidthWidgetProps {
  bandwidth: BandwidthStats | null;
  isConnected: boolean;
}

export function BandwidthWidget({ bandwidth, isConnected }: BandwidthWidgetProps) {
  if (!bandwidth) return null;

  const totalBytes = bandwidth.up_bytes + bandwidth.down_bytes;
  const limit = 200 * 1024 * 1024 * 1024;
  const percent = Math.min((totalBytes / limit) * 100, 100);

  return (
    <div className="px-1">
      <div className="mb-2 flex items-center gap-1.5">
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            isConnected ? 'bg-emerald-400 shadow-[0_0_4px_rgba(74,222,128,0.5)]' : 'bg-rose-400'
          )}
          title={isConnected ? 'Connected to Telegram' : 'Disconnected — check your internet'}
        />
        <span className="text-slate text-[11px] font-medium">
          {formatBytes(totalBytes)} <span className="text-stone">/ 200 GB daily</span>
        </span>
      </div>
      <div className="border-hairline-soft h-1.5 w-full overflow-hidden rounded-full border bg-surface-soft">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 1.5, ease: "circOut" }}
          className="bg-primary h-full rounded-full"
        />
      </div>
    </div>
  );
}
