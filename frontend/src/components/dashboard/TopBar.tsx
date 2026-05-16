import { useEffect, useRef } from 'react';
import { HardDrive, LayoutGrid, List, Settings, Search, ChevronRight, FolderInput, Download, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/cn';

interface TopBarProps {
    currentFolderName: string;
    selectedIds: number[];
    onShowMoveModal: () => void;
    onBulkDownload: () => void;
    onBulkDelete: () => void;
    onDownloadFolder: () => void;
    viewMode: 'grid' | 'list';
    setViewMode: (mode: 'grid' | 'list') => void;
    searchTerm: string;
    onSearchChange: (term: string) => void;
    onSettingsClick: () => void;
}

export function TopBar({
    currentFolderName, selectedIds, onShowMoveModal, onBulkDownload, onBulkDelete,
    onDownloadFolder, viewMode, setViewMode, searchTerm, onSearchChange, onSettingsClick
}: TopBarProps) {
    const searchRef = useRef<HTMLInputElement>(null);

    // Cmd/Ctrl + K focuses search (a Linear-style nicety, no logic added beyond DOM focus)
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                searchRef.current?.focus();
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    const hasSelection = selectedIds.length > 0;

    return (
        <header
            className="h-14 px-4 flex items-center justify-between gap-4 border-b border-hairline bg-canvas/80 backdrop-blur-md sticky top-0 z-10"
            onClick={(e) => e.stopPropagation()}
        >
            {/* Breadcrumbs */}
            <nav className="flex items-center gap-1.5 text-[13px] select-none min-w-0">
                <span className="text-stone hover:text-foreground cursor-pointer transition-colors">Start</span>
                <ChevronRight className="w-3.5 h-3.5 text-stone shrink-0" />
                <span className="text-foreground font-medium truncate">{currentFolderName}</span>
            </nav>

            {/* Search — cmd+k-style command pill */}
            <div className="flex-1 max-w-md">
                <label
                    className={cn(
                        'group flex items-center gap-2.5 h-9 pl-3 pr-2 rounded-md',
                        'bg-white/[0.03] border border-hairline-strong/70',
                        'focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20',
                        'transition-colors',
                    )}
                >
                    <Search className="w-3.5 h-3.5 text-stone shrink-0" />
                    <input
                        ref={searchRef}
                        type="text"
                        placeholder="Search files…"
                        value={searchTerm}
                        onChange={(e) => onSearchChange(e.target.value)}
                        className="flex-1 bg-transparent text-[13px] text-foreground placeholder:text-stone outline-none"
                    />
                    <kbd className="hidden sm:flex items-center gap-0.5 h-5 px-1.5 rounded text-[10px] font-medium text-stone bg-white/[0.04] border border-hairline shrink-0">
                        <span className="text-[11px] leading-none">⌘</span>K
                    </kbd>
                </label>
            </div>

            {/* Actions cluster */}
            <div className="flex items-center gap-1">
                {/* Multi-select action group */}
                {hasSelection && (
                    <div className="flex items-center gap-1.5 mr-2 pr-2 border-r border-hairline animate-in fade-in slide-in-from-top-1 duration-200">
                        <span className="text-[11px] text-stone mr-1 px-1">{selectedIds.length} selected</span>
                        <Button variant="secondary" size="sm" onClick={onShowMoveModal} className="h-7 text-[12px]">
                            <FolderInput className="w-3.5 h-3.5" />
                            Move
                        </Button>
                        <Button variant="ghost" size="sm" onClick={onBulkDownload} className="h-7 text-[12px]">
                            <Download className="w-3.5 h-3.5" />
                            Download
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={onBulkDelete}
                            className="h-7 text-[12px] text-rose-400 hover:bg-rose-500/10 hover:text-rose-400"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                            Delete
                        </Button>
                    </div>
                )}

                {/* Icon buttons */}
                <IconButton title="Download all files" onClick={onDownloadFolder}>
                    <HardDrive className="w-4 h-4" />
                </IconButton>

                <IconButton
                    title={viewMode === 'grid' ? 'Switch to list' : 'Switch to grid'}
                    onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                >
                    {viewMode === 'grid' ? <List className="w-4 h-4" /> : <LayoutGrid className="w-4 h-4" />}
                </IconButton>

                <span className="w-px h-5 bg-hairline mx-1" aria-hidden />

                <IconButton title="Settings" onClick={onSettingsClick}>
                    <Settings className="w-4 h-4" />
                </IconButton>
            </div>
        </header>
    );
}

function IconButton({
    children,
    title,
    onClick,
}: {
    children: React.ReactNode;
    title: string;
    onClick?: () => void;
}) {
    return (
        <button
            onClick={onClick}
            className="relative w-8 h-8 grid place-items-center rounded-md text-slate hover:text-foreground hover:bg-white/[0.04] transition-colors group"
            title={title}
        >
            {children}
            <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 text-[10px] bg-card border border-hairline px-1.5 py-0.5 rounded text-stone opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-lg">
                {title}
            </span>
        </button>
    );
}
