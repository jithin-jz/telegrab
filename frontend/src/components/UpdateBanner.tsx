import { motion, AnimatePresence } from 'framer-motion';
import { Download, X, RefreshCw, Sparkles } from 'lucide-react';

interface UpdateBannerProps {
  available: boolean;
  version: string | null;
  downloading: boolean;
  progress: number;
  onUpdate: () => void;
  onDismiss: () => void;
}

export function UpdateBanner({
  available,
  version,
  downloading,
  progress,
  onUpdate,
  onDismiss,
}: UpdateBannerProps) {
  return (
    <AnimatePresence>
      {available && (
        <motion.div
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -50 }}
          className="from-primary/90 via-link-blue/90 to-brand-purple/90 relative z-40 w-full border-b border-white/10 bg-gradient-to-r p-3 shadow-lg backdrop-blur-sm"
        >
          <div className="mx-auto flex max-w-screen-lg items-center justify-center gap-4">
            <Sparkles className="text-brand-yellow h-5 w-5 animate-pulse" />

            <span className="text-on-primary font-medium">
              {downloading ? (
                <>Downloading update... {progress}%</>
              ) : (
                <>A new version ({version}) is available!</>
              )}
            </span>

            {downloading ? (
              <div className="flex items-center gap-2">
                <RefreshCw className="text-on-primary h-4 w-4 animate-spin" />
                <div className="bg-on-primary/30 h-2 w-32 overflow-hidden rounded-full">
                  <motion.div
                    className="bg-on-primary h-full rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            ) : (
              <button
                onClick={onUpdate}
                className="bg-on-primary text-primary hover:bg-on-primary/90 flex items-center gap-2 rounded-full px-4 py-1.5 font-semibold shadow-md transition-colors"
              >
                <Download className="h-4 w-4" />
                Update Now
              </button>
            )}

            {!downloading && (
              <button
                onClick={onDismiss}
                className="text-on-primary/70 hover:text-on-primary p-1 transition-colors"
                title="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
