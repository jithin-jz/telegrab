import { BandwidthStats } from '../../types';
import { formatBytes } from '../../lib/utils';
import { motion } from 'framer-motion';

interface BandwidthWidgetProps {
  bandwidth: BandwidthStats | null;
}

export function BandwidthWidget({ bandwidth }: BandwidthWidgetProps) {
  if (!bandwidth) return null;

  const totalBytes = bandwidth.up_bytes + bandwidth.down_bytes;
  const limit = 250 * 1024 * 1024 * 1024; // 250GB
  const percent = Math.min((totalBytes / limit) * 100, 100);

  return (
    <div className="mt-4 px-1 group/bandwidth">
      <div className="mb-1.5 flex items-end justify-between">
        <span className="text-stone group-hover/bandwidth:text-slate transition-colors text-[10px] font-semibold tracking-wider uppercase">
          Daily Usage
        </span>
        <span className="text-slate text-[10px] font-medium">{percent.toFixed(1)}%</span>
      </div>
      <div className="border-hairline-soft h-2 w-full overflow-hidden rounded-full border bg-white/[0.04] p-[1px]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 1.5, ease: "circOut" }}
          className="bg-primary h-full rounded-full shadow-[0_0_8px_rgba(124,92,255,0.4)]"
        />
      </div>
      <div className="text-stone mt-1.5 flex justify-between text-[10px] font-medium">
        <span>{formatBytes(totalBytes)}</span>
        <span className="opacity-60">250 GB limit</span>
      </div>
    </div>
  );
}
