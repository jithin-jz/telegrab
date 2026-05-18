import { useState, useEffect, useCallback, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { invoke } from '../lib/platform/core';
import { toast } from 'sonner';

import { TelegramFile, BandwidthStats } from '../types';
import { fetchFiles } from '../lib/api';

// Components
import { Sidebar } from './dashboard/Sidebar';
import { TopBar } from './dashboard/TopBar';
import { FileExplorer } from './dashboard/FileExplorer';
import { UploadQueue } from './dashboard/UploadQueue';
import { DownloadQueue } from './dashboard/DownloadQueue';
import { MoveToFolderModal } from './dashboard/MoveToFolderModal';
import { PreviewModal } from './dashboard/PreviewModal';
import { MediaPlayer } from './dashboard/MediaPlayer';
import { MiniPlayer } from './dashboard/MiniPlayer';
import { DragDropOverlay } from './dashboard/DragDropOverlay';
import { ExternalDropBlocker } from './dashboard/ExternalDropBlocker';
import { PdfViewer } from './dashboard/PdfViewer';
import { SettingsModal } from './dashboard/SettingsModal';
import { CommandPalette } from './dashboard/CommandPalette';
import { UpdateBanner } from './UpdateBanner';

// Hooks
import { useTelegramConnection } from '../hooks/useTelegramConnection';
import { useFileOperations } from '../hooks/useFileOperations';
import { useFileUpload } from '../hooks/useFileUpload';
import { useFileDownload } from '../hooks/useFileDownload';
import { useSearch } from '../hooks/useSearch';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useUpdateCheck } from '../hooks/useUpdateCheck';
import { useSettings } from '../contexts/SettingsContext';
import { useDashboardSelection } from '../hooks/useDashboardSelection';
import { useDashboardPreview } from '../hooks/useDashboardPreview';

export function Dashboard({ onLogout }: { onLogout: () => void }) {
  const queryClient = useQueryClient();

  const {
    store, folders, activeFolderId, setActiveFolderId,
    isSyncing, isConnected, handleLogout, handleSyncFolders,
    handleCreateFolder, handleRenameFolder, handleFolderDelete,
  } = useTelegramConnection(onLogout);

  const { settings, updateSetting, isLoaded: settingsLoaded } = useSettings();
  const viewMode = settings.viewMode;
  const setViewMode = (mode: 'grid' | 'list') => updateSetting('viewMode', mode);

  // Auto-update
  const {
    available: updateAvailable, version: updateVersion,
    downloading: updateDownloading, progress: updateProgress,
    checkForUpdates, downloadAndInstall, dismissUpdate,
  } = useUpdateCheck();
  const startupCheckDone = useRef(false);
  useEffect(() => {
    if (!settingsLoaded || startupCheckDone.current || !settings.autoUpdate) return;
    startupCheckDone.current = true;
    checkForUpdates();
  }, [settingsLoaded, settings.autoUpdate, checkForUpdates]);

  // UI state
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [internalDragFileId, _setInternalDragFileId] = useState<number | null>(null);
  const internalDragRef = useRef<number | null>(null);
  const setInternalDragFileId = (id: number | null) => {
    internalDragRef.current = id;
    _setInternalDragFileId(id);
  };

  // Data fetching
  const { data: allFiles = [], isLoading, error } = useQuery({
    queryKey: ['files', activeFolderId],
    queryFn: () => fetchFiles(activeFolderId),
    enabled: !!store,
  });

  const { searchTerm, setSearchTerm, displayedFiles, isSearching } = useSearch({ allFiles, activeFolderId });

  const { data: bandwidth } = useQuery({
    queryKey: ['bandwidth'],
    queryFn: () => invoke<BandwidthStats>('cmd_get_bandwidth'),
    refetchInterval: 5000,
    enabled: !!store,
  });

  // Selection (extracted hook)
  const {
    selectedIds, setSelectedIds, handleFileClick,
    handleToggleSelection, handleSelectAll, handleArrowNav,
  } = useDashboardSelection(displayedFiles, activeFolderId);

  // Preview/media (extracted hook)
  const {
    previewFile, setPreviewFile, playingFile, setPlayingFile,
    pdfFile, setPdfFile, playerExpanded, setPlayerExpanded,
    contextFiles, contextIndex, openPreview,
    handleNext, handlePrev, neighbors, closeAll,
  } = useDashboardPreview(activeFolderId);

  // Upload/download
  const {
    uploadQueue, setUploadQueue, handleManualUpload,
    cancelAll: cancelUploads, cancelItem: cancelUploadItem,
    retryItem: retryUploadItem, isDragging,
  } = useFileUpload(activeFolderId, store);
  const {
    downloadQueue, queueDownload, queueBulkDownload,
    clearFinished: clearDownloads, cancelAll: cancelDownloads,
    cancelItem: cancelDownloadItem, retryItem: retryDownloadItem,
  } = useFileDownload(store);

  // File operations
  const {
    handleBulkDelete, handleBulkDownload, handleBulkMove, handleDownloadFolder,
  } = useFileOperations(activeFolderId, selectedIds, setSelectedIds, displayedFiles, queueBulkDownload);

  // Keyboard shortcuts
  const handleEscape = useCallback(() => {
    setSelectedIds([]);
    setSearchTerm('');
    closeAll();
  }, [setSelectedIds, setSearchTerm, closeAll]);

  const handleFocusSearch = useCallback(() => {
    const el = document.querySelector('input[placeholder="Search files..."]') as HTMLInputElement;
    if (el) { el.focus(); el.select(); }
  }, []);

  const handleEnter = useCallback(() => {
    if (selectedIds.length === 1) {
      const selected = displayedFiles.find((f) => f.id === selectedIds[0]);
      if (selected) {
        if (selected.type === 'folder') setActiveFolderId(selected.id);
        else openPreview(selected, displayedFiles);
      }
    }
  }, [selectedIds, displayedFiles, setActiveFolderId, openPreview]);

  useKeyboardShortcuts({
    onSelectAll: handleSelectAll,
    onDelete: selectedIds.length > 0 ? handleBulkDelete : () => {},
    onEscape: handleEscape,
    onSearch: handleFocusSearch,
    onEnter: handleEnter,
    enabled: !previewFile && !playingFile && !pdfFile && !showMoveModal,
  });

  // Ctrl+K
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setShowCommandPalette((v) => !v); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);

  // Arrow nav
  useEffect(() => {
    if (previewFile || playingFile || pdfFile || showMoveModal || showCommandPalette) return;
    const h = (e: KeyboardEvent) => handleArrowNav(e);
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [handleArrowNav, previewFile, playingFile, pdfFile, showMoveModal, showCommandPalette]);

  // Reset search/move modal on folder change
  useEffect(() => {
    setShowMoveModal(false);
    setSearchTerm('');
  }, [activeFolderId, setSearchTerm]);

  // Delete with optimistic update
  const handleDelete = async (id: number) => {
    const prev = queryClient.getQueryData<TelegramFile[]>(['files', activeFolderId]);
    if (prev) queryClient.setQueryData(['files', activeFolderId], prev.filter((f) => f.id !== id));
    try {
      await invoke('cmd_delete_file', { messageId: id, folderId: activeFolderId });
      toast.success('File deleted');
      queryClient.invalidateQueries({ queryKey: ['files', activeFolderId] });
    } catch {
      if (prev) queryClient.setQueryData(['files', activeFolderId], prev);
      toast.error('Failed to delete file');
    }
  };

  // Drag-drop on folder
  const handleDropOnFolder = async (e: React.DragEvent, targetFolderId: number | null) => {
    e.preventDefault();
    e.stopPropagation();
    if (activeFolderId === targetFolderId) return;
    const dtId = e.dataTransfer.getData('application/x-telegram-file-id');
    const fileId = internalDragRef.current || (dtId ? parseInt(dtId) : null);
    if (!fileId) return;

    const idsToMove = selectedIds.includes(fileId) ? selectedIds : [fileId];
    const prevSource = queryClient.getQueryData<TelegramFile[]>(['files', activeFolderId]);
    if (prevSource) {
      queryClient.setQueryData(['files', activeFolderId], prevSource.filter((f) => !idsToMove.includes(f.id)));
    }
    try {
      await invoke('cmd_move_files', { messageIds: idsToMove, sourceFolderId: activeFolderId, targetFolderId });
      if (selectedIds.includes(fileId)) setSelectedIds([]);
      toast.success(`Moved ${idsToMove.length} file(s).`);
      setInternalDragFileId(null);
      queryClient.invalidateQueries({ queryKey: ['files'] });
    } catch {
      if (prevSource) queryClient.setQueryData(['files', activeFolderId], prevSource);
      toast.error('Failed to move file(s).');
    }
  };

  const currentFolderName = activeFolderId === null
    ? 'Saved Messages'
    : folders.find((f) => f.id === activeFolderId)?.name || 'Folder';

  const handleRootDrag = (e: React.DragEvent) => {
    if (internalDragRef.current) { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = 'move'; }
  };

  return (
    <div className="flex w-full flex-1 flex-col overflow-hidden">
      <UpdateBanner available={updateAvailable} version={updateVersion} downloading={updateDownloading} progress={updateProgress} onUpdate={downloadAndInstall} onDismiss={dismissUpdate} />
      <div className="bg-canvas relative flex w-full min-h-0 flex-1 overflow-hidden" onClick={() => setSelectedIds([])} onDragOver={handleRootDrag} onDragEnter={handleRootDrag}>
        <ExternalDropBlocker onUploadClick={handleManualUpload} />

        <AnimatePresence>
          {showMoveModal && <MoveToFolderModal folders={folders} onClose={() => setShowMoveModal(false)} onSelect={handleBulkMove} activeFolderId={activeFolderId} key="move-modal" />}
          {playingFile && playerExpanded && <MediaPlayer file={playingFile} onClose={() => setPlayerExpanded(false)} onNext={handleNext} onPrev={handlePrev} currentIndex={contextIndex} totalItems={contextFiles.length} activeFolderId={activeFolderId} key="media-player" />}
          {pdfFile && <PdfViewer file={pdfFile} onClose={() => setPdfFile(null)} onNext={handleNext} onPrev={handlePrev} currentIndex={contextIndex} totalItems={contextFiles.length} activeFolderId={activeFolderId} key="pdf-viewer" />}
          {isDragging && internalDragFileId === null && <DragDropOverlay key="drag-drop-overlay" />}
        </AnimatePresence>

        <Sidebar folders={folders} activeFolderId={activeFolderId} setActiveFolderId={setActiveFolderId} onDrop={handleDropOnFolder} onDelete={handleFolderDelete} onCreate={handleCreateFolder} onRename={handleRenameFolder} isSyncing={isSyncing} isConnected={isConnected} onSync={handleSyncFolders} onLogout={handleLogout} bandwidth={bandwidth || null} />

        <main className="flex flex-1 flex-col" onClick={(e) => { if (e.target === e.currentTarget) setSelectedIds([]); }}>
          <TopBar currentFolderName={currentFolderName} selectedIds={selectedIds} onShowMoveModal={() => setShowMoveModal(true)} onBulkDownload={handleBulkDownload} onBulkDelete={handleBulkDelete} onDownloadFolder={handleDownloadFolder} viewMode={viewMode} setViewMode={setViewMode} searchTerm={searchTerm} onSearchChange={setSearchTerm} onSettingsClick={() => setShowSettings(true)} onNavigateHome={() => setActiveFolderId(null)} />
          {searchTerm.length > 2 && (
            <div className="px-6 pt-4 pb-0">
              <h2 className="text-telegram-subtext text-sm font-medium">Search Results for <span className="text-telegram-primary">"{searchTerm}"</span></h2>
            </div>
          )}
          <FileExplorer files={displayedFiles} loading={isLoading || isSearching} error={error} viewMode={viewMode} selectedIds={selectedIds} activeFolderId={activeFolderId} onFileClick={handleFileClick} onDelete={handleDelete} onDownload={(id, name) => queueDownload(id, name, activeFolderId)} onPreview={(file) => openPreview(file, displayedFiles)} onManualUpload={handleManualUpload} onSelectionClear={() => setSelectedIds([])} onToggleSelection={handleToggleSelection} onDrop={handleDropOnFolder} onDragStart={(fileId) => setInternalDragFileId(fileId)} onDragEnd={() => setTimeout(() => setInternalDragFileId(null), 50)} />
        </main>

        {previewFile && <PreviewModal file={previewFile} activeFolderId={activeFolderId} onClose={() => setPreviewFile(null)} onNext={handleNext} onPrev={handlePrev} currentIndex={contextIndex} totalItems={contextFiles.length} nextFile={neighbors.nextFile} prevFile={neighbors.prevFile} />}

        <div className="pointer-events-none fixed right-4 bottom-4 z-[100] flex w-[min(20rem,calc(100vw-2rem))] flex-col gap-3">
          <div className="pointer-events-auto">
            <UploadQueue items={uploadQueue} onClearFinished={() => setUploadQueue((q) => q.filter((i) => i.status !== 'success' && i.status !== 'error' && i.status !== 'cancelled'))} onCancelAll={cancelUploads} onCancelItem={cancelUploadItem} onRetryItem={retryUploadItem} />
          </div>
          <div className="pointer-events-auto">
            <DownloadQueue items={downloadQueue} onClearFinished={clearDownloads} onCancelAll={cancelDownloads} onCancelItem={cancelDownloadItem} onRetryItem={retryDownloadItem} />
          </div>
        </div>

        <AnimatePresence>
          {playingFile && !playerExpanded && <MiniPlayer key={`mini-${playingFile.id}`} file={playingFile} onClose={() => { setPlayingFile(null); setPlayerExpanded(false); }} onExpand={() => setPlayerExpanded(true)} onNext={handleNext} onPrev={handlePrev} currentIndex={contextIndex} totalItems={contextFiles.length} activeFolderId={activeFolderId} />}
        </AnimatePresence>

        <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />
        <CommandPalette open={showCommandPalette} onClose={() => setShowCommandPalette(false)} folders={folders} onNavigateFolder={setActiveFolderId} onUpload={handleManualUpload} onSettings={() => setShowSettings(true)} onSync={handleSyncFolders} onLogout={handleLogout} />
      </div>
    </div>
  );
}
