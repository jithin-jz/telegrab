import { useState, memo } from 'react';
import { HardDrive, Folder, Plus, RefreshCw, LogOut } from 'lucide-react';
import { SidebarItem } from './SidebarItem';
import { BandwidthWidget } from './BandwidthWidget';
import { TelegramFolder, BandwidthStats } from '../../types';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { cn } from '../../lib/cn';

interface SidebarProps {
  folders: TelegramFolder[];
  activeFolderId: number | null;
  setActiveFolderId: (id: number | null) => void;
  onDrop: (e: React.DragEvent, folderId: number | null) => void;
  onDelete: (id: number, name: string) => void;
  onCreate: (name: string) => Promise<void>;
  onRename: (id: number, newName: string) => Promise<void>;
  isSyncing: boolean;
  isConnected: boolean;
  onSync: () => void;
  onLogout: () => void;
  bandwidth: BandwidthStats | null;
}

export const Sidebar = memo(function Sidebar({
  folders,
  activeFolderId,
  setActiveFolderId,
  onDrop,
  onDelete,
  onCreate,
  onRename,
  isSyncing,
  isConnected,
  onSync,
  onLogout,
  bandwidth,
}: SidebarProps) {
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  const submitCreate = async () => {
    if (!newFolderName.trim()) return;
    try {
      await onCreate(newFolderName);
      setNewFolderName('');
      setShowNewFolderInput(false);
    } catch {
      // handled by parent
    }
  };

  return (
    <aside
      className="bg-canvas border-hairline flex w-[260px] shrink-0 flex-col border-r"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Brand header */}
      <div className="flex items-center gap-2.5 px-4 pt-4 pb-3">
        <div className="leading-tight">
          <div className="text-foreground text-[14px] font-semibold tracking-tight">Telegrab</div>
          <div className="text-stone text-[10px] tracking-[0.08em] uppercase">private drive</div>
        </div>
      </div>

      {/* Scrollable folder list */}
      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pt-1 pb-4">
        {/* Section: My Drive */}
        <div className="text-stone px-3 pt-2 pb-1.5 text-[10px] font-semibold tracking-[0.08em] uppercase">
          My Drive
        </div>
        <div className="space-y-0.5">
          <SidebarItem
            icon={HardDrive}
            label="Saved Messages"
            active={activeFolderId === null}
            onClick={() => setActiveFolderId(null)}
            onDrop={(e: React.DragEvent) => onDrop(e, null)}
            folderId={null}
          />
        </div>

        {/* Section: Folders */}
        <div className="flex items-center justify-between px-3 pt-4 pb-1.5">
          <span className="text-stone text-[10px] font-semibold tracking-[0.08em] uppercase">
            Folders
          </span>
          <span className="text-stone text-[10px]">{folders.length}</span>
        </div>
        <div className="space-y-0.5">
          {folders.map((folder) => (
            <SidebarItem
              key={folder.id}
              icon={Folder}
              label={folder.name}
              active={activeFolderId === folder.id}
              onClick={() => setActiveFolderId(folder.id)}
              onDrop={(e: React.DragEvent) => onDrop(e, folder.id)}
              onDelete={() => onDelete(folder.id, folder.name)}
              onRename={(newName: string) => onRename(folder.id, newName)}
              folderId={folder.id}
            />
          ))}

          {folders.length === 0 && !showNewFolderInput && (
            <div className="text-stone px-3 py-2 text-[12px] leading-relaxed">
              No folders yet. Create one to organise your files.
            </div>
          )}
        </div>
      </nav>

      {/* Sticky Create Folder section */}
      <div className="px-3 pb-3">
        {showNewFolderInput ? (
          <div className="space-y-2">
            <Input
              autoFocus
              placeholder="Folder name"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitCreate();
                if (e.key === 'Escape') {
                  setShowNewFolderInput(false);
                  setNewFolderName('');
                }
              }}
              onBlur={() => !newFolderName && setShowNewFolderInput(false)}
              className="h-9 text-[13px]"
            />
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowNewFolderInput(true)}
            className="text-slate hover:text-foreground hover:border-hairline-strong w-full justify-start border-dashed"
          >
            <Plus className="h-3.5 w-3.5" />
            Create folder
          </Button>
        )}
      </div>

      {/* Footer: connection + actions + bandwidth */}
      <div className="border-hairline space-y-3 border-t px-3 pt-3 pb-4">
        {/* Connection pill */}
        <div className="flex items-center gap-2 px-1">
          <span
            className={cn(
              'h-1.5 w-1.5 rounded-full transition-colors',
              isConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]' : 'bg-rose-400'
            )}
          />
          <span className="text-slate truncate text-[11px]">
            {isConnected ? 'Connected to Telegram' : 'Disconnected'}
          </span>
        </div>

        {/* Sync + Logout */}
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onSync}
            disabled={isSyncing}
            className="text-slate hover:text-foreground h-8 text-[12px]"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isSyncing && 'animate-spin')} />
            {isSyncing ? 'Syncing' : 'Sync'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className="text-slate h-8 text-[12px] hover:text-rose-400"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </Button>
        </div>

        {/* Bandwidth */}
        {bandwidth && <BandwidthWidget bandwidth={bandwidth} />}
      </div>
    </aside>
  );
});
