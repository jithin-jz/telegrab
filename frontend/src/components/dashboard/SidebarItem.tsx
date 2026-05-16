import { useState } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/cn';
import { useQueryClient } from '@tanstack/react-query';
import { fetchFiles } from '../../lib/api';

interface SidebarItemProps {
  icon: React.ElementType;
  label: string;
  active: boolean;
  onClick: () => void;
  onDrop: (e: React.DragEvent) => void;
  onDelete?: () => void;
  folderId: number | null;
}

/**
 * SidebarItem - Pure DOM event-based drop handling
 *
 * With Tauri's dragDropEnabled: false, DOM events work reliably.
 * This component handles internal file moves via standard React drag events.
 *
 * Linear-style: active state shown by a left accent bar + tinted bg.
 * Hover is a barely-there elevation (rgba white 0.04).
 */
export function SidebarItem({
  icon: Icon,
  label,
  active = false,
  onClick,
  onDrop,
  onDelete,
  folderId,
}: SidebarItemProps) {
  const [isOver, setIsOver] = useState(false);
  const queryClient = useQueryClient();

  const handleMouseEnter = () => {
    // Only pre-fetch if we have a folder ID and it's not the active one
    if (folderId !== undefined && !active) {
      queryClient.prefetchQuery({
        queryKey: ['files', folderId],
        queryFn: () => fetchFiles(folderId),
        staleTime: 60000, // Consider pre-fetched data fresh for 1 minute
      });
    }
  };

  return (
    <button
      onClick={onClick}
      onDragEnter={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsOver(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'move';
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX;
        const y = e.clientY;
        if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
          setIsOver(false);
        }
      }}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsOver(false);
        if (onDrop) onDrop(e);
      }}
      onContextMenu={(e) => {
        if (onDelete) {
          e.preventDefault();
          onDelete();
        }
      }}
      className={cn(
        'group relative flex w-full items-center gap-2.5 rounded-md py-1.5 pr-2 pl-3 text-[13px] font-medium transition-colors duration-150 gpu-accel-hover',
        active
          ? 'text-foreground bg-white/[0.04]'
          : 'text-slate hover:text-foreground hover:bg-white/[0.03]',
        isOver && 'bg-primary/15 text-foreground ring-primary/60 ring-1'
      )}
      onMouseEnter={handleMouseEnter}
    >
      {/* Left accent bar — only visible when active */}
      <span
        aria-hidden
        className={cn(
          'absolute top-1/2 left-0 h-4 w-[2px] -translate-y-1/2 rounded-r-full transition-opacity',
          active ? 'bg-primary opacity-100' : 'opacity-0'
        )}
      />
      <Icon
        className={cn(
          'h-4 w-4 shrink-0 transition-colors',
          active ? 'text-primary' : 'text-stone group-hover:text-slate',
          isOver && 'text-primary'
        )}
        strokeWidth={1.75}
      />
      <span className="flex-1 truncate text-left">{label}</span>
      {onDelete && (
        <span
          role="button"
          tabIndex={-1}
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="text-stone grid h-5 w-5 place-items-center rounded opacity-0 transition-colors group-hover:opacity-100 hover:bg-white/5 hover:text-rose-400"
          title="Delete folder"
        >
          <X className="h-3 w-3" />
        </span>
      )}
    </button>
  );
}
