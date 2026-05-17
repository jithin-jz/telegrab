export interface TelegramFile {
  id: number;
  name: string;
  size: number;
  sizeStr: string; // Formatted size
  created_at?: string;
  type?: 'folder' | 'file'; // implied icon_type
  // Add other fields if backend sends them
}

export interface TelegramFolder {
  id: number;
  name: string;
  parent_id?: number;
}

export interface QueueItem {
  id: string;
  path: string;
  folderId: number | null;
  status: 'pending' | 'uploading' | 'success' | 'error' | 'cancelled' | 'paused';
  error?: string;
  progress?: number; // 0-100
  uploadedBytes?: number;
  totalBytes?: number;
  speedBytesPerSec?: number;
  resumeOffset?: number; // bytes already transferred (for resume)
  skipDuplicateCheck?: boolean; // skip dedup (user chose "replace")
}

export interface BandwidthStats {
  up_bytes: number;
  down_bytes: number;
}

export interface DownloadItem {
  id: string;
  messageId: number;
  filename: string;
  folderId: number | null;
  dirPath?: string; // Pre-selected directory for bulk downloads
  status: 'pending' | 'downloading' | 'success' | 'error' | 'cancelled' | 'paused';
  error?: string;
  progress?: number; // 0-100
  uploadedBytes?: number;
  totalBytes?: number;
  speedBytesPerSec?: number;
  resumeOffset?: number; // bytes already transferred (for resume)
}
