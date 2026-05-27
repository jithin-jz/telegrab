import { motion, AnimatePresence } from 'framer-motion';
import { WifiOff } from 'lucide-react';

interface OfflineBannerProps {
  isOffline: boolean;
}

/**
 * Persistent offline banner displayed at the top of the app when network
 * connectivity is lost. Remains visible until connectivity is restored.
 *
 * Requirements: 8.1 — show persistent offline banner when connectivity lost.
 */
export function OfflineBanner({ isOffline }: OfflineBannerProps) {
  return (
    <AnimatePresence>
      {isOffline && (
        <motion.div
          initial={{ opacity: 0, y: -40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -40 }}
          transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
          className="relative z-50 w-full border-b border-amber-500/20 bg-amber-950/80 px-4 py-2.5 shadow-lg backdrop-blur-sm"
          role="alert"
          aria-live="assertive"
        >
          <div className="mx-auto flex max-w-screen-lg items-center justify-center gap-3">
            <WifiOff className="h-4 w-4 shrink-0 text-amber-400" />
            <span className="text-[13px] font-medium text-amber-200">
              You&apos;re offline. Transfers are paused. Retrying connection&hellip;
            </span>
            <span className="flex items-center gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-1 w-1 rounded-full bg-amber-400/80 animate-pulse"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
