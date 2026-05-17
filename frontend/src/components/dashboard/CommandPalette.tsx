import { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Folder, Upload, Settings, HardDrive, LogOut, RefreshCw } from 'lucide-react';
import { TelegramFolder } from '../../types';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  folders: TelegramFolder[];
  onNavigateFolder: (id: number | null) => void;
  onUpload: () => void;
  onSettings: () => void;
  onSync: () => void;
  onLogout: () => void;
}

interface CommandItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  action: () => void;
  section: string;
}

export function CommandPalette({
  open,
  onClose,
  folders,
  onNavigateFolder,
  onUpload,
  onSettings,
  onSync,
  onLogout,
}: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [
      { id: 'home', label: 'Go to Saved Messages', icon: <HardDrive className="h-4 w-4" />, action: () => onNavigateFolder(null), section: 'Navigation' },
      ...folders.map((f) => ({
        id: `folder-${f.id}`,
        label: `Go to ${f.name}`,
        icon: <Folder className="h-4 w-4" />,
        action: () => onNavigateFolder(f.id),
        section: 'Navigation',
      })),
      { id: 'upload', label: 'Upload Files', icon: <Upload className="h-4 w-4" />, action: onUpload, section: 'Actions' },
      { id: 'sync', label: 'Sync Folders', icon: <RefreshCw className="h-4 w-4" />, action: onSync, section: 'Actions' },
      { id: 'settings', label: 'Open Settings', icon: <Settings className="h-4 w-4" />, action: onSettings, section: 'Actions' },
      { id: 'logout', label: 'Logout', icon: <LogOut className="h-4 w-4" />, action: onLogout, section: 'Actions' },
    ];
    return items;
  }, [folders, onNavigateFolder, onUpload, onSettings, onSync, onLogout]);

  const filtered = useMemo(() => {
    if (!query) return commands;
    const q = query.toLowerCase();
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const runCommand = (item: CommandItem) => {
    onClose();
    item.action();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) runCommand(filtered[selectedIndex]);
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[200] flex items-start justify-center bg-black/50 backdrop-blur-sm pt-[20vh]"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: -10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -10 }}
          transition={{ duration: 0.15 }}
          className="bg-surface border-hairline w-full max-w-lg overflow-hidden rounded-xl border shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="border-hairline flex items-center gap-3 border-b px-4 py-3">
            <Search className="text-slate h-4 w-4 shrink-0" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a command..."
              className="text-foreground placeholder:text-slate w-full bg-transparent text-sm outline-none"
            />
            <kbd className="text-slate bg-surface-soft rounded px-1.5 py-0.5 text-[10px] font-medium">ESC</kbd>
          </div>
          <div className="max-h-72 overflow-y-auto p-1">
            {filtered.length === 0 && (
              <div className="text-slate px-4 py-6 text-center text-sm">No results found</div>
            )}
            {filtered.map((item, i) => (
              <button
                key={item.id}
                onClick={() => runCommand(item)}
                className={`text-foreground flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  i === selectedIndex ? 'bg-primary/10 text-primary' : 'hover:bg-surface-soft'
                }`}
              >
                <span className="shrink-0 opacity-70">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
