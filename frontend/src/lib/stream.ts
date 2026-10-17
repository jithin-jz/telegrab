import { useEffect, useState } from 'react';
import { invoke } from './platform/core';

/** Local media server details (127.0.0.1, random port, per-session token). */
export interface StreamInfo {
  token: string;
  base_url: string;
}

let infoPromise: Promise<StreamInfo> | null = null;

/** Stream server info, fetched once per session and shared by every caller. */
export function getStreamInfo(): Promise<StreamInfo> {
  if (!infoPromise) {
    infoPromise = invoke<StreamInfo>('cmd_get_stream_info').catch((err) => {
      infoPromise = null; // allow a retry on the next call
      throw err;
    });
  }
  return infoPromise;
}

export function useStreamInfo(): StreamInfo | null {
  const [info, setInfo] = useState<StreamInfo | null>(null);
  useEffect(() => {
    let cancelled = false;
    getStreamInfo()
      .then((i) => {
        if (!cancelled) setInfo(i);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return info;
}

function folderSegment(folderId: number | null): string {
  return folderId !== null ? String(folderId) : 'home';
}

/** URL of a file's byte stream (supports HTTP range requests). */
export function streamUrl(info: StreamInfo, folderId: number | null, messageId: number): string {
  return `${info.base_url}/stream/${folderSegment(folderId)}/${messageId}?token=${info.token}`;
}

export type ThumbQuality = 'low' | 'medium' | 'high';

/** URL of a file's JPEG thumbnail; cached by the webview like any image. */
export function thumbnailUrl(
  info: StreamInfo,
  folderId: number | null,
  messageId: number,
  quality: ThumbQuality = 'medium',
): string {
  return `${info.base_url}/thumb/${folderSegment(folderId)}/${messageId}?q=${quality}&token=${info.token}`;
}
