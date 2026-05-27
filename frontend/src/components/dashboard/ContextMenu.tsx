import { useEffect, useRef } from 'react';
import { Eye, HardDrive, Trash2, FolderOpen, Pencil, Play, FileText, Pin, PinOff } from 'lucide-react';
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { TelegramFile } from '../../types';
import { isMediaFile, isPdfFile } from '../../lib/utils';
import {
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '../ui/dropdown-menu';

interface ContextMenuProps {
  x: number;
  y: number;
  file: TelegramFile;
  onClose: () => void;
  onDownload: () => void;
  onDelete: () => void;
  onPreview: () => void;
  onPin?: () => void;
  onUnpin?: () => void;
  isPinned?: boolean;
}

export function ContextMenu({
  x,
  y,
  file,
  onClose,
  onDownload,
  onDelete,
  onPreview,
  onPin,
  onUnpin,
  isPinned,
}: ContextMenuProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  // Compute viewport-constrained position
  useEffect(() => {
    if (!contentRef.current) return;
    const rect = contentRef.current.getBoundingClientRect();
    let adjustedX = x;
    let adjustedY = y;

    if (x + rect.width > window.innerWidth) {
      adjustedX = x - rect.width;
    }
    if (y + rect.height > window.innerHeight) {
      adjustedY = y - rect.height;
    }

    contentRef.current.style.left = `${adjustedX}px`;
    contentRef.current.style.top = `${adjustedY}px`;
  }, [x, y]);

  return (
    <DropdownMenuPrimitive.Root open onOpenChange={(open) => !open && onClose()}>
      {/* Hidden trigger — required by Radix but not visible since we position via coordinates */}
      <DropdownMenuPrimitive.Trigger asChild>
        <span className="fixed" style={{ left: x, top: y, width: 0, height: 0 }} />
      </DropdownMenuPrimitive.Trigger>

      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          ref={contentRef}
          className="bg-surface/95 border-hairline animate-in fade-in zoom-in-95 fixed z-50 min-w-[200px] rounded-lg border p-1.5 shadow-2xl backdrop-blur-xl duration-100"
          style={{ left: x, top: y }}
          onInteractOutside={onClose}
          onEscapeKeyDown={onClose}
          onContextMenu={(e) => e.preventDefault()}
          // Disable Radix's built-in positioning so we can use fixed coordinates
          side="bottom"
          align="start"
          sideOffset={0}
          alignOffset={0}
          avoidCollisions={false}
        >
          <DropdownMenuLabel className="text-slate border-hairline mb-1 max-w-[180px] truncate border-b px-2 py-1.5 text-xs font-medium">
            {file.name}
          </DropdownMenuLabel>

          {file.type !== 'folder' && (
            <DropdownMenuItem
              onSelect={onPreview}
              className="text-foreground hover:bg-surface-soft flex w-full cursor-default items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors"
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
            </DropdownMenuItem>
          )}

          {file.type === 'folder' && (
            <DropdownMenuItem
              onSelect={onPreview}
              className="text-foreground hover:bg-surface-soft flex w-full cursor-default items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors"
            >
              <FolderOpen className="text-brand-yellow h-4 w-4" />
              Open
            </DropdownMenuItem>
          )}

          <DropdownMenuItem
            onSelect={onDownload}
            className="text-foreground hover:bg-surface-soft flex w-full cursor-default items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors"
          >
            <HardDrive className="text-brand-green h-4 w-4" />
            Download
          </DropdownMenuItem>

          <DropdownMenuItem
            disabled
            className="text-slate hover:bg-surface-soft flex w-full cursor-not-allowed items-center gap-2 rounded px-2 py-1.5 text-sm opacity-50 transition-colors"
          >
            <Pencil className="h-4 w-4" />
            Rename
          </DropdownMenuItem>

          {file.type !== 'folder' && (
            <DropdownMenuItem
              onSelect={isPinned ? onUnpin : onPin}
              className="text-foreground hover:bg-surface-soft flex w-full cursor-default items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors"
            >
              {isPinned ? (
                <>
                  <PinOff className="h-4 w-4 text-amber-400" />
                  Unpin
                </>
              ) : (
                <>
                  <Pin className="h-4 w-4 text-amber-400" />
                  Pin to Quick Access
                </>
              )}
            </DropdownMenuItem>
          )}

          <DropdownMenuSeparator className="bg-hairline my-1 h-px" />

          <DropdownMenuItem
            onSelect={onDelete}
            className="flex w-full cursor-default items-center gap-2 rounded px-2 py-1.5 text-sm text-rose-500 transition-colors hover:bg-rose-500/10"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  );
}
