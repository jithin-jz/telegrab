import { useEffect, useState } from 'react';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { TelegramFile } from '../../types';
import { isVideoFile, isAudioFile } from '../../lib/utils';

interface StreamInfo {
  token: string;
  base_url: string;
}

interface MediaPlayerProps {
  file: TelegramFile;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  currentIndex?: number;
  totalItems?: number;
  activeFolderId: number | null;
}

export function MediaPlayer({
  file,
  onClose,
  onNext,
  onPrev,
  currentIndex,
  totalItems,
  activeFolderId,
}: MediaPlayerProps) {
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null);

  useEffect(() => {
    invoke<StreamInfo>('cmd_get_stream_info')
      .then(setStreamInfo)
      .catch(() => {});
  }, []);

  const folderIdParam = activeFolderId !== null ? activeFolderId.toString() : 'home';
  const streamUrl = streamInfo
    ? `${streamInfo.base_url}/stream/${folderIdParam}/${file.id}?token=${streamInfo.token}`
    : null;

  const isVideo = isVideoFile(file.name);
  const isAudio = isAudioFile(file.name);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return;
      }

      const key = e.key.toLowerCase();

      if (e.key === 'ArrowRight' || key === 'l') {
        e.preventDefault();
        onNext?.();
        return;
      }

      if (e.key === 'ArrowLeft' || key === 'j') {
        e.preventDefault();
        onPrev?.();
        return;
      }

      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, onNext, onPrev]);

  return (
    <div
      className="animate-in fade-in fixed inset-0 z-[200] flex items-center justify-center bg-black/90 p-4 backdrop-blur-md duration-200"
      onClick={onClose}
    >
      <div
        className="relative flex w-full max-w-6xl flex-col items-center"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onPrev}
          className="absolute top-1/2 left-2 z-10 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white/50 transition-all hover:bg-white/20 hover:text-white"
          title="Previous (ArrowLeft / J)"
        >
          <ChevronLeft className="h-6 w-6" />
        </button>

        <button
          onClick={onNext}
          className="absolute top-1/2 right-2 z-10 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white/50 transition-all hover:bg-white/20 hover:text-white"
          title="Next (ArrowRight / L)"
        >
          <ChevronRight className="h-6 w-6" />
        </button>

        <button
          onClick={onClose}
          className="absolute -top-12 right-0 rounded-full bg-white/10 p-2 text-white/50 transition-all hover:bg-white/20 hover:text-white"
        >
          <X className="h-6 w-6" />
        </button>

        <div className="flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl bg-black shadow-2xl ring-1 ring-white/10">
          {!streamUrl ? (
            <div className="flex flex-col items-center gap-4 text-white">
              <div className="border-primary h-10 w-10 animate-spin rounded-full border-4 border-t-transparent"></div>
              <p>Preparing stream...</p>
            </div>
          ) : isVideo ? (
            <video src={streamUrl} controls autoPlay className="h-full w-full object-contain" />
          ) : isAudio ? (
            <div className="from-primary/20 flex h-full w-full flex-col items-center justify-center bg-gradient-to-br to-black">
              <div className="bg-surface animate-pulse-slow mb-8 flex h-32 w-32 items-center justify-center rounded-full shadow-xl">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="text-primary h-12 w-12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 18V5l12-2v13" />
                  <circle cx="6" cy="18" r="3" />
                  <circle cx="18" cy="16" r="3" />
                </svg>
              </div>
              <audio src={streamUrl} controls autoPlay className="w-full max-w-md" />
            </div>
          ) : (
            <div className="text-white">Unsupported media type</div>
          )}
        </div>

        <div className="mt-4 text-center">
          <h3 className="text-lg font-medium text-white">{file.name}</h3>
          <p className="text-sm text-white/50">
            Streaming from Telegrab
            {typeof currentIndex === 'number' &&
              typeof totalItems === 'number' &&
              totalItems > 0 && (
                <span className="ml-2">
                  • {currentIndex + 1}/{totalItems}
                </span>
              )}
          </p>
        </div>
      </div>
    </div>
  );
}
