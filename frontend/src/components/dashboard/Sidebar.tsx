import { useState } from 'react';
import { HardDrive, Folder, Plus, RefreshCw, LogOut } from 'lucide-react';
import { SidebarItem } from './SidebarItem';
import { BandwidthWidget } from './BandwidthWidget';
import { TelegramFolder, BandwidthStats } from '../../types';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { cn } from '../../lib/cn';
import logoUrl from '../../assets/logo.svg';

interface SidebarProps {
    folders: TelegramFolder[];
    activeFolderId: number | null;
    setActiveFolderId: (id: number | null) => void;
    onDrop: (e: React.DragEvent, folderId: number | null) => void;
    onDelete: (id: number, name: string) => void;
    onCreate: (name: string) => Promise<void>;
    isSyncing: boolean;
    isConnected: boolean;
    onSync: () => void;
    onLogout: () => void;
    bandwidth: BandwidthStats | null;
}

export function Sidebar({
    folders, activeFolderId, setActiveFolderId, onDrop, onDelete, onCreate,
    isSyncing, isConnected, onSync, onLogout, bandwidth
}: SidebarProps) {
    const [showNewFolderInput, setShowNewFolderInput] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");

    const submitCreate = async () => {
        if (!newFolderName.trim()) return;
        try {
            await onCreate(newFolderName);
            setNewFolderName("");
            setShowNewFolderInput(false);
        } catch {
            // handled by parent
        }
    }

    return (
        <aside
            className="w-[260px] shrink-0 bg-canvas border-r border-hairline flex flex-col"
            onClick={(e) => e.stopPropagation()}
        >
            {/* Brand header */}
            <div className="px-4 pt-4 pb-3 flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-hairline grid place-items-center shadow-sm">
                    <img src={logoUrl} className="w-7 h-7" alt="Telegrab" />
                </div>
                <div className="leading-tight">
                    <div className="text-[14px] font-semibold tracking-tight text-foreground">Telegrab</div>
                    <div className="text-[10px] text-stone uppercase tracking-[0.08em]">private drive</div>
                </div>
            </div>

            {/* Scrollable folder list */}
            <nav className="flex-1 px-2 pt-1 pb-4 overflow-y-auto min-h-0">
                {/* Section: My Drive */}
                <div className="px-3 pt-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-stone">
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
                <div className="px-3 pt-4 pb-1.5 flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-stone">Folders</span>
                    <span className="text-[10px] text-stone">{folders.length}</span>
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
                            folderId={folder.id}
                        />
                    ))}

                    {folders.length === 0 && !showNewFolderInput && (
                        <div className="px-3 py-2 text-[12px] text-stone leading-relaxed">
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
                                if (e.key === 'Escape') { setShowNewFolderInput(false); setNewFolderName(''); }
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
                        className="w-full justify-start text-slate border-dashed hover:text-foreground hover:border-hairline-strong"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        Create folder
                    </Button>
                )}
            </div>

            {/* Footer: connection + actions + bandwidth */}
            <div className="px-3 pb-4 pt-3 border-t border-hairline space-y-3">
                {/* Connection pill */}
                <div className="flex items-center gap-2 px-1">
                    <span
                        className={cn(
                            'w-1.5 h-1.5 rounded-full transition-colors',
                            isConnected
                                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]'
                                : 'bg-rose-400',
                        )}
                    />
                    <span className="text-[11px] text-slate truncate">
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
                        className="h-8 text-[12px] text-slate hover:text-foreground"
                    >
                        <RefreshCw className={cn('w-3.5 h-3.5', isSyncing && 'animate-spin')} />
                        {isSyncing ? 'Syncing' : 'Sync'}
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onLogout}
                        className="h-8 text-[12px] text-slate hover:text-rose-400"
                    >
                        <LogOut className="w-3.5 h-3.5" />
                        Sign out
                    </Button>
                </div>

                {/* Bandwidth */}
                {bandwidth && <BandwidthWidget bandwidth={bandwidth} />}
            </div>
        </aside>
    )
}
