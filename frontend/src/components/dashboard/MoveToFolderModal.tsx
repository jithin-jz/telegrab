import { useState } from 'react';
import { Plus, HardDrive, Folder } from 'lucide-react';
import { motion } from 'framer-motion';
import { TelegramFolder } from '../../types';

interface MoveToFolderModalProps {
  folders: TelegramFolder[];
  onClose: () => void;
  onSelect: (id: number | null) => void;
  activeFolderId: number | null;
}

export function MoveToFolderModal({
  folders,
  onClose,
  onSelect,
  activeFolderId,
}: MoveToFolderModalProps) {
  const [moving, setMoving] = useState(false);

  const handleSelect = (id: number | null) => {
    if (moving) return;
    setMoving(true);
    onSelect(id);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 backdrop-blur-[6px]"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: 4 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="bg-surface border-hairline flex max-h-[80vh] w-80 flex-col overflow-hidden rounded-xl border shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-hairline flex items-center justify-between border-b p-4">
          <h3 className="text-foreground font-medium">Move to Folder</h3>
          <button
            onClick={onClose}
            className="text-slate hover:text-foreground transition-colors duration-150"
          >
            <Plus className="h-5 w-5 rotate-45" />
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {activeFolderId !== null && (
            <button
              disabled={moving}
              onClick={() => handleSelect(null)}
              className="text-foreground hover:bg-surface-soft flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm transition-colors duration-150 disabled:opacity-50"
            >
              <div className="bg-primary/20 text-primary flex h-8 w-8 items-center justify-center rounded">
                <HardDrive className="h-4 w-4" />
              </div>
              <span className="font-medium">Saved Messages</span>
            </button>
          )}

          {folders.map((f: TelegramFolder) => {
            const isCurrent = f.id === activeFolderId;
            if (isCurrent) return null;
            return (
              <button
                key={f.id}
                disabled={moving}
                onClick={() => handleSelect(f.id)}
                className="text-foreground hover:bg-surface-soft flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm transition-colors duration-150 disabled:opacity-50"
              >
                <div className="bg-surface-soft text-foreground flex h-8 w-8 items-center justify-center rounded">
                  <Folder className="h-4 w-4" />
                </div>
                <span className="font-medium">{f.name}</span>
              </button>
            );
          })}

          {folders.length === 0 && activeFolderId === null && (
            <div className="text-slate p-4 text-center text-xs">
              No other folders available. Create one first!
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
