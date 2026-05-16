import { motion } from 'framer-motion';
import { UploadCloud } from 'lucide-react';

export function DragDropOverlay() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="glass bg-telegram-surface border-telegram-primary/50 text-telegram-text flex flex-col items-center gap-4 rounded-2xl border p-8 shadow-2xl"
      >
        <div className="bg-telegram-primary/10 rounded-full p-4">
          <UploadCloud className="text-telegram-primary h-12 w-12 animate-bounce" />
        </div>
        <div className="text-center">
          <h3 className="text-telegram-text text-xl font-bold">Drop files to upload</h3>
          <p className="text-telegram-subtext mt-1 text-sm">
            Files will be uploaded to the current folder
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
