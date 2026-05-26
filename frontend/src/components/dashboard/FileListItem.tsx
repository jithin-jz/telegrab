import { useState, useEffect, memo } from 'react';
import { Folder, Eye, Download, Trash2, Play } from 'lucide-react';
import { TelegramFile } from '../../types';
import { FileTypeIcon } from '../FileTypeIcon';
import { isMediaFile } from '../../lib/utils';
import { invoke } from '../../lib/platform/core';

function isImageFile(filename: string): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext);
}

interface FileListItemProps {
  file: TelegramFile;
  selectedIds: Set<number>;
  activeFolderId: number | null;
  onFileClick: (e: React.MouseEvent, id: number) => void;
  handleContextMenu: (e: React.MouseEvent, file: TelegramFile) => void;
  onDragStart?: (fileId: number) => void;
  onDragEnd?: () => void;
  onDrop?: (e: React.DragEvent, folderId: number) => void;
  onPreview: (file: TelegramFile) => void;
  onDownload: (id: number, name: string) => void;
  onDelete: (id: number) => void;
}

export const FileListItem = memo(function FileListItem({
  file,
  selectedIds,
  activeFolderId,
  onFileClick,
  handleContextMenu,
  onDragStart,
  onDragEnd,
  onDrop,
  onPreview,
  onDownload,
  onDelete,
}: FileListItemProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const isFolder = file.type === 'folder';
  const showThumb = !isFolder && isImageFile(file.name);

  // Lazy load thumbnail for image files
  useEffect(() => {
    if (!showThumb) return;
    let cancelled = false;
    invoke<string>('cmd_get_thumbnail', { messageId: file.id, folderId: activeFolderId })
      .then((result) => {
        if (!cancelled && result) setThumbnail(result);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [file.id, activeFolderId, showThumb]);

  return (
    <div
      onClick={(e) => onFileClick(e, file.id)}
      onContextMenu={(e) => handleContextMenu(e, file)}
      draggable
      onDragStart={(e) => {
        if (onDragStart) onDragStart(file.id);
        e.dataTransfer.setData('application/x-telegram-file-id', file.id.toString());
        e.dataTransfer.effectAllowed = 'move';
      }}
      onDragEnd={() => { if (onDragEnd) onDragEnd(); }}
      onDragOver={(e) => {
        if (isFolder) { e.preventDefault(); e.stopPropagation(); if (!isDragOver) setIsDragOver(true); }
      }}
      onDragLeave={(e) => {
        if (isFolder) { e.preventDefault(); e.stopPropagation(); setIsDragOver(false); }
      }}
      onDrop={(e) => {
        if (isFolder && onDrop) { e.preventDefault(); e.stopPropagation(); setIsDragOver(false); onDrop(e, file.id); }
      }}
      className={`group hover:bg-surface-soft grid cursor-pointer grid-cols-[2rem_2fr_6rem_8rem] items-center gap-4 rounded-lg border border-transparent px-4 py-2 transition-all ${selectedIds.has(file.id) ? 'bg-primary/10 border-primary/20' : ''} ${isDragOver ? 'ring-primary bg-primary/20 ring-2' : ''} `}
    >
      <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded">
        {thumbnail ? (
          <img src={thumbnail} alt="" className="h-8 w-8 rounded object-cover" />
        ) : isFolder ? (
          <Folder className="text-primary h-5 w-5" />
        ) : (
          <FileTypeIcon filename={file.name} className="h-5 w-5" />
        )}
      </div>
      <div className="text-foreground relative truncate pr-8 text-sm font-medium">
        {file.name}
        <div className="bg-surface border-hairline absolute top-1/2 right-0 flex -translate-y-1/2 items-center rounded border px-1 opacity-0 shadow-lg group-hover:opacity-100">
          <button
            onClick={(e) => { e.stopPropagation(); onPreview(file); }}
            className="hover:text-foreground text-slate p-1"
            title={isMediaFile(file.name) ? 'Play' : 'Preview'}
          >
            {isMediaFile(file.name) ? (
              <Play className="h-4 w-4 translate-x-[1px]" fill="currentColor" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDownload(file.id, file.name); }}
            className="hover:text-foreground text-slate p-1"
            title="Download"
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(file.id); }}
            className="text-slate p-1 hover:text-rose-400"
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="text-slate truncate text-right text-xs">{file.sizeStr}</div>
      <div className="text-slate truncate text-right font-mono text-xs opacity-50">
        {file.created_at || '-'}
      </div>
    </div>
  );
});
