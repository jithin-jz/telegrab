import { useEffect, useRef, useState } from 'react';
import { Eye, HardDrive, Trash2, FolderOpen, Pencil, Play, FileText } from 'lucide-react';
import { TelegramFile } from '../../types';
import { isMediaFile, isPdfFile } from '../../lib/utils';

interface ContextMenuProps {
  x: number;
  y: number;
  file: TelegramFile;
  onClose: () => void;
  onDownload: () => void;
  onDelete: () => void;
  onPreview: () => void;
}

export function ContextMenu({
  x,
  y,
  file,
  onClose,
  onDownload,
  onDelete,
  onPreview,
}: ContextMenuProps) {
  const [adjustedPos, setAdjustedPos] = useState({ x, y });
  const menuRef = useRef<HTMLDivElement>(null);

  // Adjust position to stay in bounds
  useEffect(() => {
    if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      let newX = x;
      let newY = y;

      if (x + rect.width > window.innerWidth) {
        newX = x - rect.width;
      }
      if (y + rect.height > window.innerHeight) {
        newY = y - rect.height;
      }
      setAdjustedPos({ x: newX, y: newY });
    }
  }, [x, y]);

  // Close on outside click
  useEffect(() => {
    const handleClick = () => onClose();
    const handleResize = () => onClose();

    window.addEventListener('click', handleClick);
    window.addEventListener('resize', handleResize);
    window.addEventListener('contextmenu', handleClick); // Close if right click elsewhere

    return () => {
      window.removeEventListener('click', handleClick);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('contextmenu', handleClick);
    };
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="bg-surface/95 border-hairline animate-in fade-in zoom-in-95 fixed z-50 flex min-w-[200px] flex-col gap-0.5 rounded-lg border p-1.5 shadow-2xl backdrop-blur-xl duration-100"
      style={{ left: adjustedPos.x, top: adjustedPos.y }}
      onClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="text-slate border-hairline mb-1 max-w-[180px] truncate border-b px-2 py-1.5 text-xs font-medium">
        {file.name}
      </div>

      {file.type !== 'folder' && (
        <button
          onClick={onPreview}
          className="text-foreground hover:bg-surface-soft flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors"
        >
          {isMediaFile(file.name) ? (
            <>
              <Play className="text-primary h-4 w-4" />
              Play
            </>
          ) : isPdfFile(file.name) ? (
            <>
              <FileText className="h-4 w-4 text-red-400" />
              View PDF
            </>
          ) : (
            <>
              <Eye className="text-link-blue h-4 w-4" />
              Preview
            </>
          )}
        </button>
      )}

      {file.type === 'folder' && (
        <button
          onClick={onPreview}
          className="text-foreground hover:bg-surface-soft flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors"
        >
          <FolderOpen className="text-brand-yellow h-4 w-4" />
          Open
        </button>
      )}

      <button
        onClick={onDownload}
        className="text-foreground hover:bg-surface-soft flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors"
      >
        <HardDrive className="text-brand-green h-4 w-4" />
        Download
      </button>

      <button
        disabled
        className="text-slate hover:bg-surface-soft flex w-full cursor-not-allowed items-center gap-2 rounded px-2 py-1.5 text-left text-sm opacity-50 transition-colors"
      >
        <Pencil className="h-4 w-4" />
        Rename
      </button>

      <div className="bg-hairline my-1 h-px" />

      <button
        onClick={onDelete}
        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-rose-500 transition-colors hover:bg-rose-500/10"
      >
        <Trash2 className="h-4 w-4" />
        Delete
      </button>
    </div>
  );
}
