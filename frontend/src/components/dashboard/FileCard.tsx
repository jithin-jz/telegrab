import { motion } from 'framer-motion';
import { useState, useEffect, memo } from 'react';
import { Folder, Eye, Trash2, Download, Check, Play } from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { TelegramFile } from '../../types';
import { FileTypeIcon } from '../FileTypeIcon';
import { cn } from '../../lib/cn';
import { useQueryClient } from '@tanstack/react-query';
import { fetchFiles } from '../../lib/api';
import { isMediaFile } from '../../lib/utils';

interface FileCardProps {
  file: TelegramFile;
  onDelete: () => void;
  onDownload: () => void;
  onPreview?: () => void;
  isSelected: boolean;
  onClick?: (e: React.MouseEvent) => void;
  onContextMenu?: (e: React.MouseEvent) => void;
  onDrop?: (e: React.DragEvent, folderId: number) => void;
  onDragStart?: (fileId: number) => void;
  onDragEnd?: () => void;
  activeFolderId?: number | null;
  height?: number;
  onToggleSelection?: () => void;
}

// Check if file is an image type that can have a thumbnail
function isImageFile(filename: string): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext);
}

export const FileCard = memo(function FileCard({
  file,
  onDelete,
  onDownload,
  onPreview,
  isSelected,
  onClick,
  onContextMenu,
  onDrop,
  onDragStart,
  onDragEnd,
  activeFolderId,
  height,
  onToggleSelection,
}: FileCardProps) {
  const isFolder = file.type === 'folder';
  const [isDragOver, setIsDragOver] = useState(false);
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const [thumbnailLoading, setThumbnailLoading] = useState(false);
  const queryClient = useQueryClient();

  const handleMouseEnter = () => {
    if (isFolder) {
      queryClient.prefetchQuery({
        queryKey: ['files', file.id],
        queryFn: () => fetchFiles(file.id),
        staleTime: 120000, // 2 mins
      });
    }
  };

  // Lazy load thumbnail for image files
  useEffect(() => {
    if (isFolder || !isImageFile(file.name)) return;

    let cancelled = false;
    setThumbnailLoading(true);

    invoke<string>('cmd_get_thumbnail', {
      messageId: file.id,
      folderId: activeFolderId,
    })
      .then((result) => {
        if (!cancelled && result) {
          setThumbnail(result);
        }
      })
      .catch(() => {
        // Silently fail - will show icon instead
      })
      .finally(() => {
        if (!cancelled) setThumbnailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [file.id, file.name, activeFolderId, isFolder]);

  return (
    <div
      className="relative gpu-accel-hover"
      onContextMenu={onContextMenu}
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onDragOver={(e) => {
        if (isFolder) {
          e.preventDefault();
          e.stopPropagation();
          if (!isDragOver) setIsDragOver(true);
        }
      }}
      onDragLeave={(e) => {
        if (isFolder) {
          e.preventDefault();
          e.stopPropagation();
          setIsDragOver(false);
        }
      }}
      onDrop={(e) => {
        if (isFolder && onDrop) {
          e.preventDefault();
          e.stopPropagation();
          setIsDragOver(false);
          onDrop(e, file.id);
        }
      }}
    >
      <motion.div
        draggable={!isFolder}
        onDragStart={(e) => {
          const dragEvent = e as unknown as React.DragEvent<HTMLDivElement>;
          if (onDragStart) onDragStart(file.id);
          dragEvent.dataTransfer.setData('application/x-telegram-file-id', file.id.toString());
          dragEvent.dataTransfer.effectAllowed = 'move';
        }}
        onDragEnd={() => {
          if (onDragEnd) onDragEnd();
        }}
        whileHover={{ y: -1 }}
        transition={{ duration: 0.16, ease: [0.4, 0, 0.2, 1] }}
        className={cn(
          'group relative cursor-pointer overflow-hidden rounded-xl border transition-colors duration-150',
          'bg-card gpu-accel',
          isSelected
            ? 'border-primary/60 bg-primary/[0.04] shadow-[0_0_0_1px_var(--color-primary)]'
            : 'border-hairline hover:border-hairline-strong',
          isDragOver && 'border-primary/80 bg-primary/[0.08] scale-[1.012]'
        )}
        style={height ? { height: `${height}px` } : { aspectRatio: '4/3' }}
      >
        {/* Thumbnail or icon background */}
        {thumbnail ? (
          <div className="absolute inset-0">
            <img
              src={thumbnail}
              alt={file.name}
              className="h-full w-full object-cover"
              loading="lazy"
              decoding="async"
            />
            {/* gradient overlay for label readability */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
          </div>
        ) : (
          <div className="absolute inset-x-0 top-0 bottom-[64px] flex items-center justify-center">
            {/* subtle radial tint behind the icon */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-60"
              style={{
                background:
                  'radial-gradient(60% 60% at 50% 45%, rgba(124,92,255,0.10) 0%, transparent 70%)',
              }}
            />
            {isFolder ? (
              <Folder className="text-primary relative h-10 w-10" strokeWidth={1.5} />
            ) : thumbnailLoading && isImageFile(file.name) ? (
              <div className="border-primary/30 border-t-primary relative h-7 w-7 animate-spin rounded-full border-2" />
            ) : (
              <div className="relative">
                <FileTypeIcon filename={file.name} size="lg" />
              </div>
            )}
          </div>
        )}

        {/* Selection circle (top-left) */}
        <div
          onClick={(e) => {
            e.stopPropagation();
            if (onToggleSelection) onToggleSelection();
          }}
          className={cn(
            'absolute top-2.5 left-2.5 z-10 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full border transition-all',
            isSelected
              ? 'bg-primary border-primary scale-100'
              : 'border-white/30 bg-black/40 opacity-0 backdrop-blur-sm group-hover:opacity-100'
          )}
        >
          {isSelected && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
        </div>

        {/* Action buttons (top-right) — appear on hover */}
        <div className="absolute top-2 right-2 z-10 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          {onPreview && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPreview();
              }}
              className={cn(
                'grid h-7 w-7 place-items-center rounded-md bg-black/60 text-white/80 backdrop-blur transition-colors duration-150 hover:text-white',
                isMediaFile(file.name) ? 'hover:bg-primary' : 'hover:bg-primary'
              )}
              title={isMediaFile(file.name) ? 'Play' : 'Preview'}
            >
              {isMediaFile(file.name) ? (
                <Play className="h-3.5 w-3.5 translate-x-[1px]" fill="currentColor" />
              ) : (
                <Eye className="h-3.5 w-3.5" />
              )}
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDownload();
            }}
            className="grid h-7 w-7 place-items-center rounded-md bg-black/60 text-white/80 backdrop-blur transition-colors hover:bg-emerald-500 hover:text-white"
            title="Download"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="grid h-7 w-7 place-items-center rounded-md bg-black/60 text-white/80 backdrop-blur transition-colors hover:bg-rose-500 hover:text-white"
            title="Delete"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Filename + size strip at the bottom */}
        <div
          className={cn(
            'absolute right-0 bottom-0 left-0 border-t px-3 py-2.5',
            thumbnail
              ? 'border-transparent text-white'
              : 'border-hairline-soft bg-card/60 backdrop-blur-[2px]'
          )}
        >
          <h3
            className={cn(
              'truncate text-[13px] leading-snug font-medium',
              thumbnail ? 'text-white' : 'text-foreground'
            )}
            title={file.name}
          >
            {file.name}
          </h3>
          <p className={cn('mt-0.5 text-[11px]', thumbnail ? 'text-white/70' : 'text-slate')}>
            {file.sizeStr}
          </p>
        </div>
      </motion.div>
    </div>
  );
});
