import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { invoke } from '../lib/platform/core';
import { toast } from 'sonner';

import { TelegramFile, BandwidthStats } from '../types';
import { isMediaFile, isPdfFile } from '../lib/utils';
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

export function Dashboard({ onLogout }: { onLogout: () => void }) {
  const queryClient = useQueryClient();

  const {
    store,
    folders,
    activeFolderId,
    setActiveFolderId,
    isSyncing,
    isConnected,
    handleLogout,
    handleSyncFolders,
    handleCreateFolder,
    handleRenameFolder,
    handleFolderDelete,
  } = useTelegramConnection(onLogout);

  const { settings, updateSetting, isLoaded: settingsLoaded } = useSettings();
  const viewMode = settings.viewMode;
  const setViewMode = (mode: 'grid' | 'list') => updateSetting('viewMode', mode);

  // Auto-update check: runs once when the dashboard mounts and the user
  // has `Automatic Updates` turned on. The UpdateBanner stays mounted
  // throughout the session and lets the user dismiss / install.
  const {
    available: updateAvailable,
    version: updateVersion,
    downloading: updateDownloading,
    progress: updateProgress,
    checkForUpdates,
    downloadAndInstall,
    dismissUpdate,
  } = useUpdateCheck();
  const startupCheckDone = useRef(false);
  useEffect(() => {
    if (!settingsLoaded) return;
    if (startupCheckDone.current) return;
    if (!settings.autoUpdate) return;
    startupCheckDone.current = true;
    // Fire-and-forget; failures are swallowed inside the hook.
    checkForUpdates();
  }, [settingsLoaded, settings.autoUpdate, checkForUpdates]);

  const [previewFile, setPreviewFile] = useState<TelegramFile | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [internalDragFileId, _setInternalDragFileId] = useState<number | null>(null);
  const internalDragRef = useRef<number | null>(null);

  const setInternalDragFileId = (id: number | null) => {
    internalDragRef.current = id;
    _setInternalDragFileId(id);
  };
  const [playingFile, setPlayingFile] = useState<TelegramFile | null>(null);
  const [playerExpanded, setPlayerExpanded] = useState(false);
  const [pdfFile, setPdfFile] = useState<TelegramFile | null>(null);
  const [previewContextFiles, setPreviewContextFiles] = useState<TelegramFile[]>([]);
  const [previewContextIndex, setPreviewContextIndex] = useState(-1);

  const {
    data: allFiles = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['files', activeFolderId],
    queryFn: () => fetchFiles(activeFolderId),
    enabled: !!store,
  });

  const { searchTerm, setSearchTerm, displayedFiles, isSearching } = useSearch({
    allFiles,
    activeFolderId,
  });

  const { data: bandwidth } = useQuery({
    queryKey: ['bandwidth'],
    queryFn: () => invoke<BandwidthStats>('cmd_get_bandwidth'),
    refetchInterval: 5000,
    enabled: !!store,
  });

  const {
    uploadQueue,
    setUploadQueue,
    handleManualUpload,
    cancelAll: cancelUploads,
    cancelItem: cancelUploadItem,
    retryItem: retryUploadItem,
    isDragging,
  } = useFileUpload(activeFolderId, store);
  const {
    downloadQueue,
    queueDownload,
    queueBulkDownload,
    clearFinished: clearDownloads,
    cancelAll: cancelDownloads,
    cancelItem: cancelDownloadItem,
    retryItem: retryDownloadItem,
  } = useFileDownload(store);

  const {
    handleBulkDelete,
    handleBulkDownload,
    handleBulkMove,
    handleDownloadFolder,
  } = useFileOperations(activeFolderId, selectedIds, setSelectedIds, displayedFiles, queueBulkDownload);

  const handleSelectAll = useCallback(() => {
    setSelectedIds(displayedFiles.map((f: TelegramFile) => f.id));
  }, [displayedFiles]);

  const handleKeyboardDelete = useCallback(() => {
    if (selectedIds.length > 0) {
      handleBulkDelete();
    }
  }, [selectedIds, handleBulkDelete]);

  const handleEscape = useCallback(() => {
    setSelectedIds([]);
    setSearchTerm('');
    setPreviewFile(null);
    setPlayingFile(null);
    setPlayerExpanded(false);
    setPdfFile(null);
  }, []);

  const handleFocusSearch = useCallback(() => {
    const searchInput = document.querySelector(
      'input[placeholder="Search files..."]'
    ) as HTMLInputElement;
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }, []);

  const handleEnter = useCallback(() => {
    if (selectedIds.length === 1) {
      const selected = displayedFiles.find((f: TelegramFile) => f.id === selectedIds[0]);
      if (selected) {
        if (selected.type === 'folder') {
          setActiveFolderId(selected.id);
        } else {
          handlePreview(selected, displayedFiles);
        }
      }
    }
  }, [selectedIds, displayedFiles, setActiveFolderId]);

  useKeyboardShortcuts({
    onSelectAll: handleSelectAll,
    onDelete: handleKeyboardDelete,
    onEscape: handleEscape,
    onSearch: handleFocusSearch,
    onEnter: handleEnter,
    enabled: !previewFile && !playingFile && !pdfFile && !showMoveModal, // Disable when modals are open
  });

  // Ctrl+K command palette
  useEffect(() => {
    const handleCmdK = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowCommandPalette((v) => !v);
      }
    };
    window.addEventListener('keydown', handleCmdK);
    return () => window.removeEventListener('keydown', handleCmdK);
  }, []);

  // Arrow key navigation in file explorer
  useEffect(() => {
    const handleArrowNav = (e: KeyboardEvent) => {
      if (previewFile || playingFile || pdfFile || showMoveModal || showCommandPalette) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        const ids = displayedFiles.map((f) => f.id);
        if (ids.length === 0) return;

        const currentIdx = selectedIds.length > 0 ? ids.indexOf(selectedIds[selectedIds.length - 1]) : -1;
        let nextIdx: number;

        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
          nextIdx = currentIdx < ids.length - 1 ? currentIdx + 1 : 0;
        } else {
          nextIdx = currentIdx > 0 ? currentIdx - 1 : ids.length - 1;
        }

        if (e.shiftKey) {
          setSelectedIds((prev) => [...new Set([...prev, ids[nextIdx]])]);
        } else {
          setSelectedIds([ids[nextIdx]]);
        }
        lastClickedRef.current = ids[nextIdx];
      }
    };
    window.addEventListener('keydown', handleArrowNav);
    return () => window.removeEventListener('keydown', handleArrowNav);
  }, [displayedFiles, selectedIds, previewFile, playingFile, pdfFile, showMoveModal, showCommandPalette]);

  useEffect(() => {
    setSelectedIds([]);
    setShowMoveModal(false);
    setSearchTerm('');
    setPreviewFile(null);
    setPlayingFile(null);
    setPlayerExpanded(false);
    setPdfFile(null);
    setPreviewContextFiles([]);
    setPreviewContextIndex(-1);
  }, [activeFolderId]);

  const lastClickedRef = useRef<number | null>(null);

  const handleFileClick = useCallback(
    (e: React.MouseEvent, id: number) => {
      e.stopPropagation();
      if (e.shiftKey && lastClickedRef.current !== null) {
        // Range select: select all files between last clicked and current
        const ids = displayedFiles.map((f) => f.id);
        const lastIdx = ids.indexOf(lastClickedRef.current);
        const currIdx = ids.indexOf(id);
        if (lastIdx !== -1 && currIdx !== -1) {
          const start = Math.min(lastIdx, currIdx);
          const end = Math.max(lastIdx, currIdx);
          const range = ids.slice(start, end + 1);
          setSelectedIds((prev) => [...new Set([...prev, ...range])]);
          return;
        }
      }
      if (e.metaKey || e.ctrlKey) {
        setSelectedIds((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
      } else {
        setSelectedIds([id]);
      }
      lastClickedRef.current = id;
    },
    [displayedFiles]
  );

  const handleToggleSelection = useCallback((id: number) => {
    setSelectedIds((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }, []);

  const handlePreview = (file: TelegramFile, orderedFiles?: TelegramFile[]) => {
    const contextFiles = (orderedFiles || displayedFiles).filter((f: TelegramFile) => f.type !== 'folder');
    const contextIndex = contextFiles.findIndex((f: TelegramFile) => f.id === file.id);

    setPreviewContextFiles(contextFiles);
    setPreviewContextIndex(contextIndex);

    const isMedia = isMediaFile(file.name);
    const isPdf = isPdfFile(file.name);

    if (isMedia) {
      setPlayingFile(file);
      setPreviewFile(null);
      setPdfFile(null);
    } else if (isPdf) {
      setPdfFile(file);
      setPreviewFile(null);
      setPlayingFile(null);
    } else {
      setPreviewFile(file);
      setPlayingFile(null);
      setPdfFile(null);
    }
  };

  const navigatePreview = useCallback(
    (step: 1 | -1) => {
      if (previewContextFiles.length === 0) return;

      const currentFileId = previewFile?.id ?? playingFile?.id ?? pdfFile?.id;
      if (!currentFileId) return;

      const currentIndex = previewContextFiles.findIndex((f: TelegramFile) => f.id === currentFileId);
      if (currentIndex === -1) return;

      const nextIndex =
        (currentIndex + step + previewContextFiles.length) % previewContextFiles.length;
      const nextFile = previewContextFiles[nextIndex];
      if (!nextFile) return;

      setPreviewContextIndex(nextIndex);

      const isMedia = isMediaFile(nextFile.name);
      const isPdf = isPdfFile(nextFile.name);

      if (isMedia) {
        setPlayingFile(nextFile);
        setPreviewFile(null);
        setPdfFile(null);
      } else if (isPdf) {
        setPdfFile(nextFile);
        setPreviewFile(null);
        setPlayingFile(null);
      } else {
        setPreviewFile(nextFile);
        setPlayingFile(null);
        setPdfFile(null);
      }
    },
    [previewContextFiles, previewFile, playingFile, pdfFile]
  );

  const handleNextPreview = useCallback(() => {
    navigatePreview(1);
  }, [navigatePreview]);

  const handlePrevPreview = useCallback(() => {
    navigatePreview(-1);
  }, [navigatePreview]);

  const previewNeighbors = useMemo(() => {
    if (previewContextFiles.length === 0) {
      return { nextFile: null as TelegramFile | null, prevFile: null as TelegramFile | null };
    }

    const currentFileId = previewFile?.id ?? playingFile?.id ?? pdfFile?.id;
    if (!currentFileId) {
      return { nextFile: null as TelegramFile | null, prevFile: null as TelegramFile | null };
    }

    const currentIdx = previewContextFiles.findIndex((f: TelegramFile) => f.id === currentFileId);
    if (currentIdx === -1) {
      return { nextFile: null as TelegramFile | null, prevFile: null as TelegramFile | null };
    }

    const nextIdx = (currentIdx + 1) % previewContextFiles.length;
    const prevIdx = (currentIdx - 1 + previewContextFiles.length) % previewContextFiles.length;

    return {
      nextFile: previewContextFiles[nextIdx] || null,
      prevFile: previewContextFiles[prevIdx] || null,
    };
  }, [previewContextFiles, previewFile, playingFile, pdfFile]);

  const handleDelete = async (id: number) => {
    // Optimistic update
    const previousFiles = queryClient.getQueryData<TelegramFile[]>(['files', activeFolderId]);
    if (previousFiles) {
      queryClient.setQueryData(
        ['files', activeFolderId],
        previousFiles.filter((f) => f.id !== id)
      );
    }

    try {
      await invoke('cmd_delete_file', { messageId: id, folderId: activeFolderId });
      toast.success('File deleted');
      // Invalidate to ensure sync
      queryClient.invalidateQueries({ queryKey: ['files', activeFolderId] });
    } catch (e) {
      // Rollback
      if (previousFiles) {
        queryClient.setQueryData(['files', activeFolderId], previousFiles);
      }
      toast.error('Failed to delete file');
    }
  };

  const handleDropOnFolder = async (e: React.DragEvent, targetFolderId: number | null) => {
    e.preventDefault();
    e.stopPropagation();

    const dataTransferFileId = e.dataTransfer.getData('application/x-telegram-file-id');

    if (activeFolderId === targetFolderId) return;

    const fileId =
      internalDragRef.current || (dataTransferFileId ? parseInt(dataTransferFileId) : null);

    if (fileId) {
      const idsToMove = selectedIds.includes(fileId) ? selectedIds : [fileId];

      // Optimistic update
      const sourceKey = ['files', activeFolderId];
      const targetKey = ['files', targetFolderId];

      const prevSource = queryClient.getQueryData<TelegramFile[]>(sourceKey);
      const prevTarget = queryClient.getQueryData<TelegramFile[]>(targetKey);

      if (prevSource) {
        const movedFiles = prevSource.filter((f) => idsToMove.includes(f.id));
        queryClient.setQueryData(
          sourceKey,
          prevSource.filter((f) => !idsToMove.includes(f.id))
        );

        if (prevTarget) {
          queryClient.setQueryData(targetKey, [...prevTarget, ...movedFiles]);
        }
      }

      try {
        await invoke('cmd_move_files', {
          messageIds: idsToMove,
          sourceFolderId: activeFolderId,
          targetFolderId: targetFolderId,
        });

        if (selectedIds.includes(fileId)) setSelectedIds([]);
        toast.success(`Moved ${idsToMove.length} file(s).`);
        setInternalDragFileId(null);

        // Invalidate to ensure consistency
        queryClient.invalidateQueries({ queryKey: ['files'] });
      } catch {
        // Rollback
        if (prevSource) queryClient.setQueryData(sourceKey, prevSource);
        if (prevTarget) queryClient.setQueryData(targetKey, prevTarget);
        toast.error(`Failed to move file(s).`);
      }
    }
  };

  const currentFolderName =
    activeFolderId === null
      ? 'Saved Messages'
      : folders.find((f) => f.id === activeFolderId)?.name || 'Folder';

  const handleRootDragOver = (e: React.DragEvent) => {
    if (internalDragRef.current) {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = 'move';
    }
  };

  const handleRootDragEnter = (e: React.DragEvent) => {
    if (internalDragRef.current) {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = 'move';
    }
  };

  // previewNeighbors is now a memoized object

  return (
    <div className="flex w-full flex-1 flex-col overflow-hidden">
      <UpdateBanner
        available={updateAvailable}
        version={updateVersion}
        downloading={updateDownloading}
        progress={updateProgress}
        onUpdate={downloadAndInstall}
        onDismiss={dismissUpdate}
      />
      <div
        className="bg-canvas relative flex w-full min-h-0 flex-1 overflow-hidden"
        onClick={() => setSelectedIds([])}
        onDragOver={handleRootDragOver}
        onDragEnter={handleRootDragEnter}
      >
      <ExternalDropBlocker onUploadClick={handleManualUpload} />

      <AnimatePresence>
        {showMoveModal && (
          <MoveToFolderModal
            folders={folders}
            onClose={() => setShowMoveModal(false)}
            onSelect={handleBulkMove}
            activeFolderId={activeFolderId}
            key="move-modal"
          />
        )}
        {playingFile && playerExpanded && (
          <MediaPlayer
            file={playingFile}
            onClose={() => setPlayerExpanded(false)}
            onNext={handleNextPreview}
            onPrev={handlePrevPreview}
            currentIndex={previewContextIndex}
            totalItems={previewContextFiles.length}
            activeFolderId={activeFolderId}
            key="media-player"
          />
        )}
        {pdfFile && (
          <PdfViewer
            file={pdfFile}
            onClose={() => setPdfFile(null)}
            onNext={handleNextPreview}
            onPrev={handlePrevPreview}
            currentIndex={previewContextIndex}
            totalItems={previewContextFiles.length}
            activeFolderId={activeFolderId}
            key="pdf-viewer"
          />
        )}
        {isDragging && internalDragFileId === null && <DragDropOverlay key="drag-drop-overlay" />}
      </AnimatePresence>

      <Sidebar
        folders={folders}
        activeFolderId={activeFolderId}
        setActiveFolderId={setActiveFolderId}
        onDrop={handleDropOnFolder}
        onDelete={handleFolderDelete}
        onCreate={handleCreateFolder}
        onRename={handleRenameFolder}
        isSyncing={isSyncing}
        isConnected={isConnected}
        onSync={handleSyncFolders}
        onLogout={handleLogout}
        bandwidth={bandwidth || null}
      />

      <main
        className="flex flex-1 flex-col"
        onClick={(e) => {
          if (e.target === e.currentTarget) setSelectedIds([]);
        }}
      >
        <TopBar
          currentFolderName={currentFolderName}
          selectedIds={selectedIds}
          onShowMoveModal={() => setShowMoveModal(true)}
          onBulkDownload={handleBulkDownload}
          onBulkDelete={handleBulkDelete}
          onDownloadFolder={handleDownloadFolder}
          viewMode={viewMode}
          setViewMode={setViewMode}
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          onSettingsClick={() => setShowSettings(true)}
          onNavigateHome={() => setActiveFolderId(null)}
        />
        {searchTerm.length > 2 && (
          <div className="px-6 pt-4 pb-0">
            <h2 className="text-telegram-subtext text-sm font-medium">
              Search Results for <span className="text-telegram-primary">"{searchTerm}"</span>
            </h2>
          </div>
        )}
        <FileExplorer
          files={displayedFiles}
          loading={isLoading || isSearching}
          error={error}
          viewMode={viewMode}
          selectedIds={selectedIds}
          activeFolderId={activeFolderId}
          onFileClick={handleFileClick}
          onDelete={handleDelete}
          onDownload={(id, name) => queueDownload(id, name, activeFolderId)}
          onPreview={handlePreview}
          onManualUpload={handleManualUpload}
          onSelectionClear={() => setSelectedIds([])}
          onToggleSelection={handleToggleSelection}
          onDrop={handleDropOnFolder}
          onDragStart={(fileId) => setInternalDragFileId(fileId)}
          onDragEnd={() => setTimeout(() => setInternalDragFileId(null), 50)}
        />
      </main>

      {previewFile && (
        <PreviewModal
          file={previewFile}
          activeFolderId={activeFolderId}
          onClose={() => setPreviewFile(null)}
          onNext={handleNextPreview}
          onPrev={handlePrevPreview}
          currentIndex={previewContextIndex}
          totalItems={previewContextFiles.length}
          nextFile={previewNeighbors.nextFile}
          prevFile={previewNeighbors.prevFile}
        />
      )}

      <div className="pointer-events-none fixed right-4 bottom-4 z-[100] flex w-[min(20rem,calc(100vw-2rem))] flex-col gap-3">
        <div className="pointer-events-auto">
          <UploadQueue
            items={uploadQueue}
            onClearFinished={() =>
              setUploadQueue((q) =>
                q.filter(
                  (i) => i.status !== 'success' && i.status !== 'error' && i.status !== 'cancelled'
                )
              )
            }
            onCancelAll={cancelUploads}
            onCancelItem={cancelUploadItem}
            onRetryItem={retryUploadItem}
          />
        </div>
        <div className="pointer-events-auto">
          <DownloadQueue
            items={downloadQueue}
            onClearFinished={clearDownloads}
            onCancelAll={cancelDownloads}
            onCancelItem={cancelDownloadItem}
            onRetryItem={retryDownloadItem}
          />
        </div>
      </div>

      {/* Persistent mini media player (Spotify-style audio bar / YouTube-style
          video card). Lifts to expanded MediaPlayer above when the user
          clicks the maximise button. */}
      <AnimatePresence>
        {playingFile && !playerExpanded && (
          <MiniPlayer
            key={`mini-${playingFile.id}`}
            file={playingFile}
            onClose={() => {
              setPlayingFile(null);
              setPlayerExpanded(false);
            }}
            onExpand={() => setPlayerExpanded(true)}
            onNext={handleNextPreview}
            onPrev={handlePrevPreview}
            currentIndex={previewContextIndex}
            totalItems={previewContextFiles.length}
            activeFolderId={activeFolderId}
          />
        )}
      </AnimatePresence>

      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />
      <CommandPalette
        open={showCommandPalette}
        onClose={() => setShowCommandPalette(false)}
        folders={folders}
        onNavigateFolder={setActiveFolderId}
        onUpload={handleManualUpload}
        onSettings={() => setShowSettings(true)}
        onSync={handleSyncFolders}
        onLogout={handleLogout}
      />
      </div>
    </div>
  );
}
