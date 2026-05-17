import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Pin, PinOff, FileText } from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { toast } from 'sonner';
import { formatBytes } from '../../lib/utils';

interface PinnedFile {
  message_id: number;
  folder_id: number | null;
  name: string;
  size: number;
  pinned_at: number;
}

interface QuickAccessProps {
  onFileClick: (messageId: number, folderId: number | null) => void;
  activeFolderId: number | null;
}

export function QuickAccess({ onFileClick }: QuickAccessProps) {
  const queryClient = useQueryClient();

  const { data: pinnedFiles = [] } = useQuery({
    queryKey: ['pinned-files'],
    queryFn: () => invoke<PinnedFile[]>('cmd_get_pinned_files'),
  });

  const handleUnpin = async (messageId: number, folderId: number | null) => {
    try {
      await invoke('cmd_unpin_file', { messageId, folderId });
      queryClient.invalidateQueries({ queryKey: ['pinned-files'] });
      toast.success('Unpinned');
    } catch {
      toast.error('Failed to unpin');
    }
  };

  if (pinnedFiles.length === 0) return null;

  return (
    <div className="border-hairline mx-4 mb-3 border-b pb-3">
      <div className="text-slate mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide">
        <Pin className="h-3 w-3" />
        Quick Access
      </div>
      <div className="flex flex-wrap gap-1.5">
        {pinnedFiles.slice(0, 8).map((file) => (
          <button
            key={`${file.message_id}-${file.folder_id}`}
            onClick={() => onFileClick(file.message_id, file.folder_id)}
            className="bg-surface-soft hover:bg-primary/10 border-hairline group flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-xs transition-colors"
            title={`${file.name} (${formatBytes(file.size)})`}
          >
            <FileText className="text-slate h-3 w-3 shrink-0" />
            <span className="text-foreground max-w-[100px] truncate">{file.name}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleUnpin(file.message_id, file.folder_id);
              }}
              className="text-slate hover:text-danger ml-0.5 hidden shrink-0 group-hover:block"
            >
              <PinOff className="h-3 w-3" />
            </button>
          </button>
        ))}
      </div>
    </div>
  );
}

export async function pinFile(messageId: number, folderId: number | null, name: string, size: number) {
  await invoke('cmd_pin_file', { messageId, folderId, name, size });
}

export async function unpinFile(messageId: number, folderId: number | null) {
  await invoke('cmd_unpin_file', { messageId, folderId });
}
