import { BandwidthStats } from '../../types';
import { formatBytes } from '../../lib/utils';

interface BandwidthWidgetProps {
    bandwidth: BandwidthStats | null;
}

export function BandwidthWidget({ bandwidth }: BandwidthWidgetProps) {
    if (!bandwidth) return null;

    const totalBytes = bandwidth.up_bytes + bandwidth.down_bytes;
    const limit = 250 * 1024 * 1024 * 1024; // 250GB
    const percent = Math.min((totalBytes / limit) * 100, 100);

    return (
        <div className="mt-4 px-1">
            <div className="flex justify-between items-end mb-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-stone">Daily Usage</span>
                <span className="text-[10px] font-medium text-slate">{percent.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-white/[0.04] border border-hairline-soft rounded-full h-2 overflow-hidden p-[1px]">
                <div
                    className="bg-primary h-full rounded-full transition-all duration-700 ease-out shadow-[0_0_8px_rgba(124,92,255,0.4)]"
                    style={{ width: `${percent}%` }}
                ></div>
            </div>
            <div className="flex justify-between text-[10px] mt-1.5 text-stone font-medium">
                <span>{formatBytes(totalBytes)}</span>
                <span>250 GB</span>
            </div>
        </div>
    );
}
