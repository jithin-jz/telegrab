import { useState, useCallback, useMemo, useEffect } from 'react';
import { TelegramFile } from '../types';
import { isMediaFile, isPdfFile } from '../lib/utils';

export function useDashboardPreview(activeFolderId: number | null) {
  const [previewFile, setPreviewFile] = useState<TelegramFile | null>(null);
  const [playingFile, setPlayingFile] = useState<TelegramFile | null>(null);
  const [pdfFile, setPdfFile] = useState<TelegramFile | null>(null);
  const [playerExpanded, setPlayerExpanded] = useState(false);
  const [contextFiles, setContextFiles] = useState<TelegramFile[]>([]);
  const [contextIndex, setContextIndex] = useState(-1);

  // Reset on folder change
  useEffect(() => {
    setPreviewFile(null);
    setPlayingFile(null);
    setPlayerExpanded(false);
    setPdfFile(null);
    setContextFiles([]);
    setContextIndex(-1);
  }, [activeFolderId]);

  const openPreview = useCallback((file: TelegramFile, orderedFiles: TelegramFile[]) => {
    const files = orderedFiles.filter((f) => f.type !== 'folder');
    const idx = files.findIndex((f) => f.id === file.id);
    setContextFiles(files);
    setContextIndex(idx);

    if (isMediaFile(file.name)) {
      setPlayingFile(file);
      setPreviewFile(null);
      setPdfFile(null);
    } else if (isPdfFile(file.name)) {
      setPdfFile(file);
      setPreviewFile(null);
      setPlayingFile(null);
    } else {
      setPreviewFile(file);
      setPlayingFile(null);
      setPdfFile(null);
    }
  }, []);

  const navigatePreview = useCallback(
    (step: 1 | -1) => {
      if (contextFiles.length === 0) return;
      const currentId = previewFile?.id ?? playingFile?.id ?? pdfFile?.id;
      if (!currentId) return;
      const currentIdx = contextFiles.findIndex((f) => f.id === currentId);
      if (currentIdx === -1) return;

      const nextIdx = (currentIdx + step + contextFiles.length) % contextFiles.length;
      const next = contextFiles[nextIdx];
      if (!next) return;

      setContextIndex(nextIdx);
      if (isMediaFile(next.name)) {
        setPlayingFile(next);
        setPreviewFile(null);
        setPdfFile(null);
      } else if (isPdfFile(next.name)) {
        setPdfFile(next);
        setPreviewFile(null);
        setPlayingFile(null);
      } else {
        setPreviewFile(next);
        setPlayingFile(null);
        setPdfFile(null);
      }
    },
    [contextFiles, previewFile, playingFile, pdfFile]
  );

  const handleNext = useCallback(() => navigatePreview(1), [navigatePreview]);
  const handlePrev = useCallback(() => navigatePreview(-1), [navigatePreview]);

  const neighbors = useMemo(() => {
    if (contextFiles.length === 0) return { nextFile: null as TelegramFile | null, prevFile: null as TelegramFile | null };
    const currentId = previewFile?.id ?? playingFile?.id ?? pdfFile?.id;
    if (!currentId) return { nextFile: null as TelegramFile | null, prevFile: null as TelegramFile | null };
    const idx = contextFiles.findIndex((f) => f.id === currentId);
    if (idx === -1) return { nextFile: null as TelegramFile | null, prevFile: null as TelegramFile | null };
    return {
      nextFile: contextFiles[(idx + 1) % contextFiles.length] || null,
      prevFile: contextFiles[(idx - 1 + contextFiles.length) % contextFiles.length] || null,
    };
  }, [contextFiles, previewFile, playingFile, pdfFile]);

  const closeAll = useCallback(() => {
    setPreviewFile(null);
    setPlayingFile(null);
    setPlayerExpanded(false);
    setPdfFile(null);
  }, []);

  return {
    previewFile,
    setPreviewFile,
    playingFile,
    setPlayingFile,
    pdfFile,
    setPdfFile,
    playerExpanded,
    setPlayerExpanded,
    contextFiles,
    contextIndex,
    openPreview,
    handleNext,
    handlePrev,
    neighbors,
    closeAll,
  };
}
