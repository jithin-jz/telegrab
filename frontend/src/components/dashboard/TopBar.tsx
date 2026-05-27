import { useEffect, useRef } from 'react';
import {
  HardDrive,
  LayoutGrid,
  List,
  Settings,
  Search,
  ChevronRight,
  FolderInput,
  Download,
  Trash2,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { cn } from '../../lib/utils';
import type { ViewMode } from '../../contexts/SettingsContext';

interface TopBarProps {
  currentFolderName: string;
  selectedIds: number[];
  onShowMoveModal: () => void;
  onBulkDownload: () => void;
  onBulkDelete: () => void;
  onDownloadFolder: () => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  searchTerm: string;
  onSearchChange: (term: string) => void;
  onSettingsClick: () => void;
  onNavigateHome: () => void;
}

import { useQueryClient } from '@tanstack/react-query';
import { fetchFiles } from '../../lib/api';

export function TopBar({
  currentFolderName,
  selectedIds,
  onShowMoveModal,
  onBulkDownload,
  onBulkDelete,
  onDownloadFolder,
  viewMode,
  setViewMode,
  searchTerm,
  onSearchChange,
  onSettingsClick,
  onNavigateHome,
}: TopBarProps) {
  const searchRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  // Predictive pre-fetching when hovering over home/root breadcrumb
  const handleHomeMouseEnter = () => {
    queryClient.prefetchInfiniteQuery({
      queryKey: ['files', null],
      queryFn: ({ pageParam }) => fetchFiles(null, pageParam),
      initialPageParam: undefined,
      staleTime: 120000,
    });
  };

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
      className="border-hairline bg-canvas/80 sticky top-0 z-10 flex h-14 items-center justify-between gap-4 border-b px-4 backdrop-blur-md"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Breadcrumbs */}
      <nav className="flex min-w-0 items-center gap-1.5 text-[13px] select-none">
        <span
          onClick={onNavigateHome}
          onMouseEnter={handleHomeMouseEnter}
          className="text-stone hover:text-foreground cursor-pointer transition-colors"
        >
          Start
        </span>
        <ChevronRight className="text-stone h-3.5 w-3.5 shrink-0" />
        <span className="text-foreground truncate font-medium">{currentFolderName}</span>
      </nav>

      {/* Search */}
      <div className="max-w-md flex-1">
        <div
          className={cn(
            'group flex h-9 items-center gap-2.5 rounded-md pr-2 pl-3',
            'border-hairline-strong/70 border bg-white/[0.03]',
            'focus-within:border-primary/70 focus-within:ring-primary/45 focus-within:ring-1',
            'transition-[border-color,box-shadow,background-color]'
          )}
          role="search"
        >
          <Search className="text-stone h-3.5 w-3.5 shrink-0" />
          <Input
            ref={searchRef}
            type="text"
            placeholder="Search files..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search files"
            className="search-input text-foreground placeholder:text-stone h-full min-w-0 flex-1 border-0 bg-transparent px-0 py-0 text-[13px]"
          />
          <kbd className="border-hairline text-stone hidden h-5 shrink-0 items-center rounded border bg-white/[0.04] px-1.5 text-[10px] font-medium sm:flex">
            Ctrl K
          </kbd>
        </div>
      </div>

      {/* Actions cluster */}
      <div className="flex items-center gap-1">
        {/* Multi-select action group */}
        {hasSelection && (
          <div className="border-hairline animate-in fade-in slide-in-from-top-1 mr-2 flex items-center gap-1.5 border-r pr-2 duration-200">
            <span className="text-stone mr-1 px-1 text-[11px]">{selectedIds.length} selected</span>
            <Button
              variant="secondary"
              size="sm"
              onClick={onShowMoveModal}
              className="h-7 text-[12px]"
            >
              <FolderInput className="h-3.5 w-3.5" />
              Move
            </Button>
            <Button variant="ghost" size="sm" onClick={onBulkDownload} className="h-7 text-[12px]">
              <Download className="h-3.5 w-3.5" />
              Download
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onBulkDelete}
              className="h-7 text-[12px] text-rose-400 hover:bg-rose-500/10 hover:text-rose-400"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </Button>
          </div>
        )}

        {/* Icon buttons */}
        <IconButton title="Download all files" onClick={onDownloadFolder}>
          <HardDrive className="h-4 w-4" />
        </IconButton>

        <ViewModeDropdown viewMode={viewMode} setViewMode={setViewMode} />

        <span className="bg-hairline mx-1 h-5 w-px" aria-hidden />

        <IconButton title="Settings" onClick={onSettingsClick}>
          <Settings className="h-4 w-4" />
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
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          aria-label={title}
          className="text-slate hover:text-foreground grid h-8 w-8 place-items-center rounded-md transition-colors hover:bg-surface-soft"
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent>
        <p>{title}</p>
      </TooltipContent>
    </Tooltip>
  );
}


const VIEW_CYCLE: ViewMode[] = ['large-grid', 'medium-grid', 'list'];

const VIEW_ICONS: Record<ViewMode, React.ReactNode> = {
  'large-grid': <LayoutGrid className="h-4 w-4" />,
  'medium-grid': <LayoutGrid className="h-4 w-4" />,
  'list': <List className="h-4 w-4" />,
};

const VIEW_LABELS: Record<ViewMode, string> = {
  'large-grid': 'Large icons',
  'medium-grid': 'Medium icons',
  'list': 'List',
};

function ViewModeDropdown({ viewMode, setViewMode }: { viewMode: ViewMode; setViewMode: (m: ViewMode) => void }) {
  const handleClick = () => {
    const idx = VIEW_CYCLE.indexOf(viewMode);
    const next = VIEW_CYCLE[(idx + 1) % VIEW_CYCLE.length];
    setViewMode(next);
  };

  const ariaLabel = viewMode === 'list' ? 'List view' : 'Grid view';

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={handleClick}
          aria-label={ariaLabel}
          className="text-slate hover:text-foreground grid h-8 w-8 place-items-center rounded-md transition-colors hover:bg-surface-soft"
        >
          {VIEW_ICONS[viewMode]}
        </button>
      </TooltipTrigger>
      <TooltipContent>
        <p>{VIEW_LABELS[viewMode]}</p>
      </TooltipContent>
    </Tooltip>
  );
}

