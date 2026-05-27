import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { Plus, ArrowUpDown, ArrowUp, ArrowDown, UploadCloud, Loader2, RefreshCw } from 'lucide-react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { FileCard } from './FileCard';
import { EmptyState } from './EmptyState';
import { TelegramFile } from '../../types';
import { ContextMenu } from './ContextMenu';
import { FileListItem } from './FileListItem';
import { cn } from '../../lib/utils';

type SortField = 'name' | 'size' | 'date';
type SortDirection = 'asc' | 'desc';
type ExplorerItem = TelegramFile | 'upload';

interface FileExplorerProps {
  files: TelegramFile[];
  loading: boolean;
  error: Error | null;
  viewMode: 'large-grid' | 'medium-grid' | 'list';
  selectedIds: number[];
  activeFolderId: number | null;
  inFlightIds?: Set<number>;
  onFileClick: (e: React.MouseEvent, id: number) => void;
  onDelete: (id: number) => void;
  onDownload: (id: number, name: string) => void;
  onPreview: (file: TelegramFile, orderedFiles?: TelegramFile[]) => void;
  onManualUpload: () => void;
  onSelectionClear: () => void;
  onToggleSelection: (id: number) => void;
  onDrop?: (e: React.DragEvent, folderId: number) => void;
  onDragStart?: (fileId: number) => void;
  onDragEnd?: () => void;
  /** Pagination: call to load the next page of files */
  onFetchNextPage?: () => void;
  /** Pagination: whether more pages are available */
  hasNextPage?: boolean;
  /** Pagination: whether the next page is currently being fetched */
  isFetchingNextPage?: boolean;
  /** Pagination: whether the last page fetch failed (for inline retry) */
  pageFetchError?: boolean;
}

function useGridColumns(containerRef: React.RefObject<HTMLDivElement | null>, viewMode: string) {
  const [columns, setColumns] = useState(4);
  const [containerWidth, setContainerWidth] = useState(800);

  useEffect(() => {
    if (!containerRef.current) return;

    const updateColumns = () => {
      const width = containerRef.current?.clientWidth || 800;
      setContainerWidth(width);

      if (viewMode === 'large-grid') {
        if (width < 640) setColumns(2);
        else if (width < 1024) setColumns(3);
        else setColumns(4);
      } else {
        // medium-grid (default)
        if (width < 640) setColumns(2);
        else if (width < 768) setColumns(3);
        else if (width < 1024) setColumns(4);
        else if (width < 1280) setColumns(5);
        else setColumns(6);
      }
    };

    updateColumns();
    const observer = new ResizeObserver(updateColumns);
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [containerRef, viewMode]);

  return { columns, containerWidth };
}

export function FileExplorer({
  files,
  loading,
  error,
  viewMode,
  selectedIds,
  activeFolderId,
  inFlightIds,
  onFileClick,
  onDelete,
  onDownload,
  onPreview,
  onManualUpload,
  onSelectionClear,
  onToggleSelection,
  onDrop,
  onDragStart,
  onDragEnd,
  onFetchNextPage,
  hasNextPage,
  isFetchingNextPage,
  pageFetchError,
}: FileExplorerProps) {
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    file: TelegramFile;
  } | null>(null);

  const parentRef = useRef<HTMLDivElement>(null);
  const { columns, containerWidth } = useGridColumns(parentRef, viewMode);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const GAP = 6;
  const cardWidth = (containerWidth - GAP * (columns - 1)) / columns;
  const cardHeight = cardWidth * 0.75; // aspect-[4/3]
  const rowHeight = Math.max(cardHeight + GAP, 150);

  // Scroll-near-bottom detection for pagination.
  // Triggers fetchNextPage when user scrolls within 200px of the bottom.
  useEffect(() => {
    const container = parentRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (!hasNextPage || isFetchingNextPage || !onFetchNextPage || pageFetchError) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

      if (distanceFromBottom < 200) {
        onFetchNextPage();
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [hasNextPage, isFetchingNextPage, onFetchNextPage, pageFetchError]);

  const handleRetryNextPage = useCallback(() => {
    onFetchNextPage?.();
  }, [onFetchNextPage]);

  const handleContextMenu = useCallback((e: React.MouseEvent, file: TelegramFile) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, file });
  }, []);

  const sortedFiles = useMemo(() => {
    return [...files].sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'size':
          comparison = (a.size || 0) - (b.size || 0);
          break;
        case 'date':
          comparison = (a.created_at || '').localeCompare(b.created_at || '');
          break;
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [files, sortField, sortDirection]);

  const handlePreviewRequest = useCallback(
    (file: TelegramFile) => {
      onPreview(file, sortedFiles);
    },
    [onPreview, sortedFiles]
  );

  const gridRows = useMemo(() => {
    const rows: ExplorerItem[][] = [];
    const itemsWithUpload: ExplorerItem[] = ['upload', ...sortedFiles];
    for (let i = 0; i < itemsWithUpload.length; i += columns) {
      rows.push(itemsWithUpload.slice(i, i + columns));
    }
    return rows;
  }, [sortedFiles, columns]);

  const listItems = useMemo(() => {
    return ['upload' as const, ...sortedFiles];
  }, [sortedFiles]);

  const gridVirtualizer = useVirtualizer({
    count: gridRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => rowHeight, [rowHeight]),
    overscan: 4,
    gap: GAP,
  });

  // Keep virtualizer in sync with resize
  useEffect(() => {
    gridVirtualizer.measure();
  }, [rowHeight, gridVirtualizer, containerWidth]);

  const listVirtualizer = useVirtualizer({
    count: listItems.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => 56, []), // matched to List Item height
    overscan: 10,
  });

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-30" />;
    return sortDirection === 'asc' ? (
      <ArrowUp className="text-primary h-3 w-3" />
    ) : (
      <ArrowDown className="text-primary h-3 w-3" />
    );
  };

  if (loading) {
    return (
      <div className="flex flex-1 flex-col p-6 animate-in fade-in duration-200 ease-out">
        <div className="flex items-center gap-4 mb-8">
          <div className="h-8 w-32 bg-white/[0.04] rounded-md animate-pulse" />
          <div className="h-8 w-32 bg-white/[0.04] rounded-md animate-pulse" />
        </div>
        <div className={cn(
          "grid gap-6",
          viewMode.includes('grid') 
            ? viewMode === 'large-grid'
              ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4'
              : 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6'
            : "grid-cols-1"
        )}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div 
              key={i} 
              className={cn(
                "bg-white/[0.03] border border-hairline rounded-xl animate-pulse",
                viewMode.includes('grid') ? "aspect-[4/3]" : "h-14"
              )} 
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-red-400">
        Error loading files
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="smooth-scroll flex-1 overflow-auto p-6">
        <EmptyState onUpload={onManualUpload} />
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      className="custom-scrollbar flex-1 overflow-auto p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onSelectionClear();
      }}
    >
      {viewMode.includes('grid') ? (
        <>
          <div className="text-slate mb-4 flex items-center justify-between gap-3 text-xs">
            <div className="flex min-w-0 items-center gap-2">
              <span className="text-slate font-medium">Sort</span>
              <button
                onClick={() => handleSort('name')}
                className={`hover:text-foreground flex h-7 items-center gap-1.5 rounded-md border border-transparent px-2.5 transition-colors hover:bg-white/5 ${sortField === 'name' ? 'text-primary bg-primary/10 border-primary/20' : ''}`}
              >
                Name <SortIcon field="name" />
              </button>
              <button
                onClick={() => handleSort('size')}
                className={`hover:text-foreground flex h-7 items-center gap-1.5 rounded-md border border-transparent px-2.5 transition-colors hover:bg-white/5 ${sortField === 'size' ? 'text-primary bg-primary/10 border-primary/20' : ''}`}
              >
                Size <SortIcon field="size" />
              </button>
              <button
                onClick={() => handleSort('date')}
                className={`hover:text-foreground flex h-7 items-center gap-1.5 rounded-md border border-transparent px-2.5 transition-colors hover:bg-white/5 ${sortField === 'date' ? 'text-primary bg-primary/10 border-primary/20' : ''}`}
              >
                Date <SortIcon field="date" />
              </button>
            </div>
            <span className="text-stone hidden text-[11px] sm:block">
              {files.length} item{files.length === 1 ? '' : 's'}
            </span>
          </div>

          <div
            role="grid"
            aria-label="File explorer"
            className="relative w-full"
            style={{ height: `${gridVirtualizer.getTotalSize()}px` }}
          >
            {gridVirtualizer.getVirtualItems().map((virtualRow) => {
              const row = gridRows[virtualRow.index];
              return (
                <div
                  key={virtualRow.key}
                  role="row"
                  className="absolute top-0 left-0 grid w-full"
                  style={{
                    height: `${cardHeight}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                    gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                    gap: `${GAP}px`,
                  }}
                >
                  {row.map((item) => {
                    if (item === 'upload') {
                      return (
                        <div key="upload" role="gridcell">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onManualUpload();
                          }}
                          aria-label="Upload file"
                          className="border-primary/35 text-slate hover:border-primary hover:text-foreground hover:bg-primary/[0.06] group bg-card/60 flex w-full flex-col items-center justify-center rounded-xl border border-dashed transition-all"
                          style={{ height: `${cardHeight}px` }}
                        >
                          <div className="bg-primary/10 border-primary/20 group-hover:bg-primary/15 mb-3 grid h-11 w-11 place-items-center rounded-lg border transition-colors">
                            <UploadCloud className="text-primary h-5 w-5 transition-transform group-hover:scale-110" />
                          </div>
                          <span className="text-foreground text-sm font-medium">Upload file</span>
                          <span className="text-stone mt-1 text-[11px]">Add to this folder</span>
                        </button>
                        </div>
                      );
                    }
                    const file = item;
                    return (
                      <div key={file.id} role="gridcell" aria-selected={selectedSet.has(file.id)}>
                      <FileCard
                        file={file}
                        isSelected={selectedSet.has(file.id)}
                        disabled={inFlightIds?.has(file.id) ?? false}
                        onClick={(e) => onFileClick(e, file.id)}
                        onContextMenu={(e) => handleContextMenu(e, file)}
                        onDelete={() => onDelete(file.id)}
                        onDownload={() => onDownload(file.id, file.name)}
                        onPreview={() => handlePreviewRequest(file)}
                        onDrop={onDrop}
                        onDragStart={onDragStart}
                        onDragEnd={onDragEnd}
                        activeFolderId={activeFolderId}
                        height={cardHeight}
                        onToggleSelection={() => onToggleSelection(file.id)}
                      />
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <div className="flex w-full flex-col">
          {/* List Header */}
          <div className="text-slate border-hairline bg-canvas mb-2 grid grid-cols-[2rem_2fr_6rem_8rem] items-center gap-4 border-b px-4 py-2 text-xs font-semibold select-none">
            <div className="text-center">#</div>
            <button
              onClick={() => handleSort('name')}
              className="hover:text-foreground flex items-center gap-1 transition-colors"
            >
              Name <SortIcon field="name" />
            </button>
            <button
              onClick={() => handleSort('size')}
              className="hover:text-foreground flex items-center justify-end gap-1 transition-colors"
            >
              Size <SortIcon field="size" />
            </button>
            <button
              onClick={() => handleSort('date')}
              className="hover:text-foreground flex items-center justify-end gap-1 transition-colors"
            >
              Date <SortIcon field="date" />
            </button>
          </div>

          <div
            className="relative w-full"
            style={{ height: `${listVirtualizer.getTotalSize()}px` }}
          >
            {listVirtualizer.getVirtualItems().map((virtualItem) => {
              const item = listItems[virtualItem.index];
              if (item === 'upload') {
                return (
                  <div
                    key="upload"
                    className="absolute top-0 left-0 w-full"
                    style={{ transform: `translateY(${virtualItem.start}px)` }}
                  >
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onManualUpload();
                      }}
                      className="border-primary/35 text-slate hover:text-foreground hover:bg-primary/[0.06] hover:border-primary/70 flex w-full cursor-pointer items-center gap-4 rounded-lg border border-dashed px-4 py-3 transition-colors"
                    >
                      <div className="bg-primary/10 text-primary border-primary/20 flex h-8 w-8 items-center justify-center rounded-md border">
                        <Plus className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 text-left">
                        <span className="text-foreground block text-sm font-medium">
                          Upload file
                        </span>
                        <span className="text-stone block text-[11px]">
                          Add files to this location
                        </span>
                      </div>
                    </button>
                  </div>
                );
              }
              const file = item;
              return (
                <div
                  key={file.id}
                  className="absolute top-0 left-0 w-full"
                  style={{ transform: `translateY(${virtualItem.start}px)` }}
                >
                  <FileListItem
                    file={file}
                    selectedIds={selectedSet}
                    activeFolderId={activeFolderId}
                    disabled={inFlightIds?.has(file.id) ?? false}
                    onFileClick={onFileClick}
                    handleContextMenu={handleContextMenu}
                    onDragStart={onDragStart}
                    onDragEnd={onDragEnd}
                    onDrop={onDrop}
                    onPreview={handlePreviewRequest}
                    onDownload={onDownload}
                    onDelete={onDelete}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pagination footer: loading spinner or retry button */}
      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="text-primary h-5 w-5 animate-spin" />
          <span className="text-slate ml-2 text-sm">Loading more files…</span>
        </div>
      )}
      {pageFetchError && !isFetchingNextPage && (
        <div className="flex items-center justify-center gap-2 py-4">
          <span className="text-red-400 text-sm">Failed to load more files</span>
          <button
            onClick={handleRetryNextPage}
            className="text-primary hover:text-primary/80 flex items-center gap-1 rounded-md border border-primary/30 px-3 py-1 text-sm transition-colors hover:bg-primary/10"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        </div>
      )}

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          file={contextMenu.file}
          onClose={() => setContextMenu(null)}
          onDownload={() => {
            onDownload(contextMenu.file.id, contextMenu.file.name);
            setContextMenu(null);
          }}
          onDelete={() => {
            onDelete(contextMenu.file.id);
            setContextMenu(null);
          }}
          onPreview={() => {
            if (contextMenu.file.type === 'folder') {
              onFileClick(
                { preventDefault: () => {}, stopPropagation: () => {} } as React.MouseEvent,
                contextMenu.file.id
              );
            } else {
              handlePreviewRequest(contextMenu.file);
            }
            setContextMenu(null);
          }}
        />
      )}
    </div>
  );
}
