import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import { Folder, Eye, Trash2, Download, Check } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { TelegramFile } from '../../types';
import { FileTypeIcon } from '../FileTypeIcon';
import { cn } from '../../lib/cn';

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

export function FileCard({ file, onDelete, onDownload, onPreview, isSelected, onClick, onContextMenu, onDrop, onDragStart, onDragEnd, activeFolderId, height, onToggleSelection }: FileCardProps) {
    const isFolder = file.type === 'folder';
    const [isDragOver, setIsDragOver] = useState(false);
    const [thumbnail, setThumbnail] = useState<string | null>(null);
    const [thumbnailLoading, setThumbnailLoading] = useState(false);

    // Lazy load thumbnail for image files
    useEffect(() => {
        if (isFolder || !isImageFile(file.name)) return;

        let cancelled = false;
        setThumbnailLoading(true);

        invoke<string>('cmd_get_thumbnail', {
            messageId: file.id,
            folderId: activeFolderId
        }).then((result) => {
            if (!cancelled && result) {
                setThumbnail(result);
            }
        }).catch(() => {
            // Silently fail - will show icon instead
        }).finally(() => {
            if (!cancelled) setThumbnailLoading(false);
        });

        return () => { cancelled = true; };
    }, [file.id, file.name, activeFolderId, isFolder]);

    return (
        <div
            className="relative"
            onContextMenu={onContextMenu}
            onClick={onClick}
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
                layout
                draggable={!isFolder}
                onDragStart={(e) => {
                    const dragEvent = e as unknown as React.DragEvent<HTMLDivElement>;
                    if (onDragStart) onDragStart(file.id);
                    dragEvent.dataTransfer.setData("application/x-telegram-file-id", file.id.toString());
                    dragEvent.dataTransfer.effectAllowed = 'move';
                }}
                onDragEnd={() => {
                    if (onDragEnd) onDragEnd();
                }}
                whileHover={{ y: -2 }}
                transition={{ type: 'spring', stiffness: 400, damping: 28 }}
                className={cn(
                    'group relative cursor-pointer overflow-hidden rounded-xl border transition-colors duration-150',
                    'bg-card',
                    isSelected
                        ? 'border-primary/60 shadow-[0_0_0_1px_var(--color-primary)] bg-primary/[0.04]'
                        : 'border-hairline hover:border-hairline-strong',
                    isDragOver && 'border-primary/80 bg-primary/[0.08] scale-[1.015]',
                )}
                style={height ? { height: `${height}px` } : { aspectRatio: '4/3' }}
            >
                {/* Thumbnail or icon background */}
                {thumbnail ? (
                    <div className="absolute inset-0">
                        <img src={thumbnail} alt={file.name} className="w-full h-full object-cover" loading="lazy" decoding="async" />
                        {/* gradient overlay for label readability */}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
                    </div>
                ) : (
                    <div className="absolute inset-x-0 top-0 bottom-[64px] flex items-center justify-center">
                        {/* subtle radial tint behind the icon */}
                        <div
                            aria-hidden
                            className="absolute inset-0 opacity-60 pointer-events-none"
                            style={{
                                background:
                                    'radial-gradient(60% 60% at 50% 45%, rgba(124,92,255,0.10) 0%, transparent 70%)',
                            }}
                        />
                        {isFolder ? (
                            <Folder className="w-10 h-10 text-primary relative" strokeWidth={1.5} />
                        ) : thumbnailLoading && isImageFile(file.name) ? (
                            <div className="w-7 h-7 border-2 border-primary/30 border-t-primary rounded-full animate-spin relative" />
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
                        'absolute top-2.5 left-2.5 w-5 h-5 rounded-full border flex items-center justify-center transition-all z-10 cursor-pointer',
                        isSelected
                            ? 'bg-primary border-primary scale-100'
                            : 'border-white/30 bg-black/40 backdrop-blur-sm opacity-0 group-hover:opacity-100',
                    )}
                >
                    {isSelected && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                </div>

                {/* Action buttons (top-right) — appear on hover */}
                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                    {onPreview && (
                        <button
                            onClick={(e) => { e.stopPropagation(); onPreview(); }}
                            className="w-7 h-7 grid place-items-center rounded-md bg-black/60 backdrop-blur text-white/80 hover:bg-primary hover:text-white transition-colors"
                            title="Preview"
                        >
                            <Eye className="w-3.5 h-3.5" />
                        </button>
                    )}
                    <button
                        onClick={(e) => { e.stopPropagation(); onDownload(); }}
                        className="w-7 h-7 grid place-items-center rounded-md bg-black/60 backdrop-blur text-white/80 hover:bg-emerald-500 hover:text-white transition-colors"
                        title="Download"
                    >
                        <Download className="w-3.5 h-3.5" />
                    </button>
                    <button
                        onClick={(e) => { e.stopPropagation(); onDelete(); }}
                        className="w-7 h-7 grid place-items-center rounded-md bg-black/60 backdrop-blur text-white/80 hover:bg-rose-500 hover:text-white transition-colors"
                        title="Delete"
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                </div>

                {/* Filename + size strip at the bottom */}
                <div
                    className={cn(
                        'absolute bottom-0 left-0 right-0 px-3 py-2.5 border-t',
                        thumbnail
                            ? 'border-transparent text-white'
                            : 'border-hairline-soft bg-card/60 backdrop-blur-[2px]',
                    )}
                >
                    <h3
                        className={cn('text-[13px] font-medium truncate leading-snug', thumbnail ? 'text-white' : 'text-foreground')}
                        title={file.name}
                    >
                        {file.name}
                    </h3>
                    <p className={cn('text-[11px] mt-0.5', thumbnail ? 'text-white/70' : 'text-slate')}>
                        {file.sizeStr}
                    </p>
                </div>
            </motion.div>
        </div>
    )
}
