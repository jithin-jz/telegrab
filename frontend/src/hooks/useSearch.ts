import { useState, useEffect, useRef, useMemo } from 'react';
import { searchFiles, fileKey } from '../lib/api';
import { TelegramFile } from '../types';

interface UseSearchOptions {
  allFiles: TelegramFile[];
  activeFolderId: number | null;
  /** Telegrab folders to include in the server-side search. */
  folderIds: number[];
}

interface UseSearchResult {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  displayedFiles: TelegramFile[];
  isSearching: boolean;
}

export function useSearch({ allFiles, activeFolderId, folderIds }: UseSearchOptions): UseSearchResult {
  const [searchTerm, setSearchTerm] = useState('');
  const [globalResults, setGlobalResults] = useState<TelegramFile[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const abortRef = useRef(0); // generation counter to cancel stale requests
  const folderIdsKey = folderIds.join(',');

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

  // Server-side search across Saved Messages + every Telegrab folder:
  // debounced, fires only for queries > 2 chars.
  useEffect(() => {
    if (searchTerm.length <= 2) {
      setGlobalResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const generation = ++abortRef.current;
    const ids = folderIdsKey ? folderIdsKey.split(',').map(Number) : [];

    const timer = setTimeout(async () => {
      try {
        const res = await searchFiles(searchTerm, ids);
        // Check if this request is still current
        if (generation !== abortRef.current) return;
        setGlobalResults(res);
      } catch {
        if (generation === abortRef.current) setGlobalResults([]);
      } finally {
        if (generation === abortRef.current) setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm, folderIdsKey]);

  // Merge local + server results. Message ids restart in every folder, so
  // files are identified by (folder, id). Results from other folders whose id
  // collides with a file shown here are dropped: the explorer keys rows by id.
  const displayedFiles = useMemo(() => {
    if (!searchTerm) return allFiles;
    if (searchTerm.length <= 2) return localResults;

    const seenKeys = new Set(localResults.map((f) => fileKey(f, activeFolderId)));
    const seenIds = new Set(localResults.map((f) => f.id));
    const merged = [...localResults];
    for (const f of globalResults) {
      const key = fileKey(f, activeFolderId);
      if (seenKeys.has(key) || seenIds.has(f.id)) continue;
      merged.push(f);
      seenKeys.add(key);
      seenIds.add(f.id);
    }
    return merged;
  }, [searchTerm, localResults, globalResults, allFiles, activeFolderId]);

  // Reset on folder change
  useEffect(() => {
    setSearchTerm('');
    setGlobalResults([]);
  }, [activeFolderId]);

  return { searchTerm, setSearchTerm, displayedFiles, isSearching };
}
