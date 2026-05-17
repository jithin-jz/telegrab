import { useState, useEffect, useRef, useMemo } from 'react';
import { invoke } from '../lib/platform/core';
import { formatBytes } from '../lib/utils';
import { TelegramFile } from '../types';

interface UseSearchOptions {
  allFiles: TelegramFile[];
  activeFolderId: number | null;
}

interface UseSearchResult {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  displayedFiles: TelegramFile[];
  isSearching: boolean;
}

export function useSearch({ allFiles, activeFolderId }: UseSearchOptions): UseSearchResult {
  const [searchTerm, setSearchTerm] = useState('');
  const [globalResults, setGlobalResults] = useState<TelegramFile[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const abortRef = useRef(0); // generation counter to cancel stale requests

  // Pre-compute lowercase names for fast local filtering
  const indexedFiles = useMemo(
    () => allFiles.map((f) => ({ file: f, lower: f.name.toLowerCase() })),
    [allFiles]
  );

  // Local filter: instant, runs on every searchTerm change
  const localResults = useMemo(() => {
    if (!searchTerm) return allFiles;
    const q = searchTerm.toLowerCase();
    // Fuzzy: split query into words, all must match
    const words = q.split(/\s+/).filter(Boolean);
    if (words.length === 0) return allFiles;
    return indexedFiles
      .filter(({ lower }) => words.every((w) => lower.includes(w)))
      .map(({ file }) => file);
  }, [searchTerm, indexedFiles, allFiles]);

  // Global search: debounced, fires only for queries > 2 chars
  useEffect(() => {
    if (searchTerm.length <= 2) {
      setGlobalResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const generation = ++abortRef.current;

    const timer = setTimeout(async () => {
      try {
        const res = await invoke<any[]>('cmd_search_global', { query: searchTerm });
        // Check if this request is still current
        if (generation !== abortRef.current) return;
        const mapped: TelegramFile[] = res.map((f) => ({
          ...f,
          sizeStr: formatBytes(f.size),
          type: f.icon_type || 'file',
        }));
        setGlobalResults(mapped);
      } catch {
        if (generation === abortRef.current) setGlobalResults([]);
      } finally {
        if (generation === abortRef.current) setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Merge: for short queries use local only; for longer queries merge local + global (deduplicated)
  const displayedFiles = useMemo(() => {
    if (!searchTerm) return allFiles;
    if (searchTerm.length <= 2) return localResults;

    // Merge local + global, deduplicate by id
    const seen = new Set(localResults.map((f) => f.id));
    const merged = [...localResults];
    for (const f of globalResults) {
      if (!seen.has(f.id)) {
        merged.push(f);
        seen.add(f.id);
      }
    }
    return merged;
  }, [searchTerm, localResults, globalResults, allFiles]);

  // Reset on folder change
  useEffect(() => {
    setSearchTerm('');
    setGlobalResults([]);
  }, [activeFolderId]);

  return { searchTerm, setSearchTerm, displayedFiles, isSearching };
}
