import { useState, useCallback, useRef, useEffect } from 'react';
import { TelegramFile } from '../types';

export function useDashboardSelection(displayedFiles: TelegramFile[], activeFolderId: number | null) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const lastClickedRef = useRef<number | null>(null);

  // Reset on folder change
  useEffect(() => {
    setSelectedIds([]);
  }, [activeFolderId]);

  const handleFileClick = useCallback(
    (e: React.MouseEvent, id: number) => {
      e.stopPropagation();
      if (e.shiftKey && lastClickedRef.current !== null) {
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

  const handleSelectAll = useCallback(() => {
    setSelectedIds(displayedFiles.map((f) => f.id));
  }, [displayedFiles]);

  const handleArrowNav = useCallback(
    (e: KeyboardEvent) => {
      if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

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
    },
    [displayedFiles, selectedIds]
  );

  return {
    selectedIds,
    setSelectedIds,
    handleFileClick,
    handleToggleSelection,
    handleSelectAll,
    handleArrowNav,
  };
}
