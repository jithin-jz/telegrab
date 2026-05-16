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
    onDismiss
}: UpdateBannerProps) {
    return (
        <AnimatePresence>
            {available && (
                <motion.div
                    initial={{ opacity: 0, y: -50 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -50 }}
                    className="fixed top-0 left-0 right-0 z-50 p-3 bg-gradient-to-r from-primary/90 via-link-blue/90 to-brand-purple/90 backdrop-blur-sm shadow-lg border-b border-white/10"
                >
                    <div className="flex items-center justify-center gap-4 max-w-screen-lg mx-auto">
                        <Sparkles className="w-5 h-5 text-brand-yellow animate-pulse" />

                        <span className="text-on-primary font-medium">
                            {downloading ? (
                                <>Downloading update... {progress}%</>
                            ) : (
                                <>A new version ({version}) is available!</>
                            )}
                        </span>

                        {downloading ? (
                            <div className="flex items-center gap-2">
                                <RefreshCw className="w-4 h-4 text-on-primary animate-spin" />
                                <div className="w-32 h-2 bg-on-primary/30 rounded-full overflow-hidden">
                                    <motion.div
                                        className="h-full bg-on-primary rounded-full"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${progress}%` }}
                                    />
                                </div>
                            </div>
                        ) : (
                            <button
                                onClick={onUpdate}
                                className="flex items-center gap-2 px-4 py-1.5 bg-on-primary text-primary font-semibold rounded-full hover:bg-on-primary/90 transition-colors shadow-md"
                            >
                                <Download className="w-4 h-4" />
                                Update Now
                            </button>
                        )}

                        {!downloading && (
                            <button
                                onClick={onDismiss}
                                className="p-1 text-on-primary/70 hover:text-on-primary transition-colors"
                                title="Dismiss"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
