import { useState } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/cn';

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
export function SidebarItem({ icon: Icon, label, active = false, onClick, onDrop, onDelete }: SidebarItemProps) {
    const [isOver, setIsOver] = useState(false);

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
                'group relative w-full flex items-center gap-2.5 pl-3 pr-2 py-1.5 rounded-md text-[13px] font-medium transition-colors duration-150',
                active
                    ? 'bg-white/[0.04] text-foreground'
                    : 'text-slate hover:bg-white/[0.03] hover:text-foreground',
                isOver && 'bg-primary/15 text-foreground ring-1 ring-primary/60',
            )}
        >
            {/* Left accent bar — only visible when active */}
            <span
                aria-hidden
                className={cn(
                    'absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-r-full transition-opacity',
                    active ? 'bg-primary opacity-100' : 'opacity-0',
                )}
            />
            <Icon
                className={cn(
                    'w-4 h-4 shrink-0 transition-colors',
                    active ? 'text-primary' : 'text-stone group-hover:text-slate',
                    isOver && 'text-primary',
                )}
                strokeWidth={1.75}
            />
            <span className="flex-1 text-left truncate">{label}</span>
            {onDelete && (
                <span
                    role="button"
                    tabIndex={-1}
                    onClick={(e) => { e.stopPropagation(); onDelete(); }}
                    className="opacity-0 group-hover:opacity-100 w-5 h-5 grid place-items-center rounded text-stone hover:text-rose-400 hover:bg-white/5 transition-colors"
                    title="Delete folder"
                >
                    <X className="w-3 h-3" />
                </span>
            )}
        </button>
    )
}
