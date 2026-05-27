import { useState } from 'react';
import { HardDrive, Folder } from 'lucide-react';
import { TelegramFolder } from '../../types';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';

interface MoveToFolderModalProps {
  isOpen: boolean;
  folders: TelegramFolder[];
  onClose: () => void;
  onSelect: (id: number | null) => void;
  activeFolderId: number | null;
}

export function MoveToFolderModal({
  isOpen,
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
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-h-[80vh] w-80 max-w-sm flex flex-col overflow-hidden p-0 gap-0">
        <DialogHeader className="border-hairline flex-row items-center justify-between border-b p-4 space-y-0">
          <DialogTitle className="text-foreground text-base font-medium">Move to Folder</DialogTitle>
        </DialogHeader>
        <div className="custom-scrollbar smooth-scroll flex-1 space-y-1 overflow-y-auto p-2">
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
      </DialogContent>
    </Dialog>
  );
}
