import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  X,
  Music2,
} from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { TelegramFile } from '../../types';
import { isVideoFile, isAudioFile } from '../../lib/utils';
import { cn } from '../../lib/cn';

interface StreamInfo {
  token: string;
  base_url: string;
}

interface MiniPlayerProps {
  file: TelegramFile;
  onClose: () => void;
  onExpand: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  currentIndex?: number;
  totalItems?: number;
  activeFolderId: number | null;
}

function fmt(t: number): string {
  if (!isFinite(t) || t < 0) return '0:00';
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/**
 * Persistent media player.
 *
 *  - Audio  → Spotify-style bar pinned to the bottom of the main area.
 *  - Video  → YouTube-style embedded card floating at the bottom-right.
 *
 * Both forms expose an "Expand" button that hands off to the full-screen
 * MediaPlayer for an immersive view.
 */
export function MiniPlayer({
  file,
  onClose,
  onExpand,
  onNext,
  onPrev,
  currentIndex,
  totalItems,
  activeFolderId,
}: MiniPlayerProps) {
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null);
  const [playing, setPlaying] = useState(true);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [scrubbing, setScrubbing] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const isVideo = isVideoFile(file.name);
  const isAudio = isAudioFile(file.name);

  const folderIdParam = activeFolderId !== null ? activeFolderId.toString() : 'home';
  const streamUrl = streamInfo
    ? `${streamInfo.base_url}/stream/${folderIdParam}/${file.id}?token=${streamInfo.token}`
    : null;

  useEffect(() => {
    invoke<StreamInfo>('cmd_get_stream_info')
      .then(setStreamInfo)
      .catch(() => {});
  }, []);

  // Reset state when the playing file changes
  useEffect(() => {
    setProgress(0);
    setDuration(0);
    setPlaying(true);
  }, [file.id]);

  const mediaEl = isVideo ? videoRef.current : audioRef.current;

  const togglePlay = () => {
    if (!mediaEl) return;
    if (mediaEl.paused) {
      mediaEl.play();
      setPlaying(true);
    } else {
      mediaEl.pause();
      setPlaying(false);
    }
  };

  const onTimeUpdate = (e: React.SyntheticEvent<HTMLMediaElement>) => {
    if (scrubbing) return;
    setProgress(e.currentTarget.currentTime);
  };

  const onLoadedMeta = (e: React.SyntheticEvent<HTMLMediaElement>) => {
    setDuration(e.currentTarget.duration);
    e.currentTarget.volume = volume;
    e.currentTarget.muted = muted;
  };

  const onEnded = () => {
    setPlaying(false);
    if (onNext) onNext();
  };

  const handleScrub = (value: number) => {
    if (!mediaEl) return;
    mediaEl.currentTime = value;
    setProgress(value);
  };

  const toggleMute = () => {
    if (!mediaEl) return;
    const next = !muted;
    mediaEl.muted = next;
    setMuted(next);
  };

  // Keyboard shortcuts (space=toggle, arrows=seek/skip, m=mute, f=fullscreen)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable) return;

      if (e.key === ' ') {
        e.preventDefault();
        togglePlay();
      } else if (e.key === 'ArrowRight' && e.shiftKey) {
        e.preventDefault();
        onNext?.();
      } else if (e.key === 'ArrowLeft' && e.shiftKey) {
        e.preventDefault();
        onPrev?.();
      } else if (e.key === 'm' || e.key === 'M') {
        toggleMute();
      } else if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        onExpand();
      } else if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [muted, onNext, onPrev, onExpand, onClose]);

  // ───────────────────────── shared transport ─────────────────────────

  const Transport = (
    <>
      <button
        onClick={onPrev}
        disabled={!onPrev || (typeof currentIndex === 'number' && currentIndex <= 0)}
        className="text-slate hover:text-foreground grid h-7 w-7 place-items-center rounded transition-colors duration-150 disabled:opacity-40 disabled:hover:text-slate"
        title="Previous (Shift+←)"
      >
        <SkipBack className="h-4 w-4" />
      </button>
      <button
        onClick={togglePlay}
        className="bg-foreground text-canvas hover:bg-foreground/90 grid h-9 w-9 place-items-center rounded-full transition-colors duration-150"
        title="Play/Pause (Space)"
      >
        {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 translate-x-[1px]" />}
      </button>
      <button
        onClick={onNext}
        disabled={
          !onNext ||
          (typeof currentIndex === 'number' &&
            typeof totalItems === 'number' &&
            currentIndex >= totalItems - 1)
        }
        className="text-slate hover:text-foreground grid h-7 w-7 place-items-center rounded transition-colors duration-150 disabled:opacity-40 disabled:hover:text-slate"
        title="Next (Shift+→)"
      >
        <SkipForward className="h-4 w-4" />
      </button>
    </>
  );

  const ProgressBar = (
    <div className="flex items-center gap-2 text-[11px] text-slate tabular-nums">
      <span>{fmt(progress)}</span>
      <input
        type="range"
        min={0}
        max={duration || 0}
        step={0.1}
        value={progress}
        onMouseDown={() => setScrubbing(true)}
        onMouseUp={() => setScrubbing(false)}
        onTouchStart={() => setScrubbing(true)}
        onTouchEnd={() => setScrubbing(false)}
        onChange={(e) => handleScrub(Number(e.target.value))}
        className="mini-player-scrubber h-1 flex-1 cursor-pointer"
        style={
          {
            '--progress':
              duration > 0 ? `${(progress / duration) * 100}%` : '0%',
          } as React.CSSProperties
        }
      />
      <span>{fmt(duration)}</span>
    </div>
  );

  const VolumeControl = (
    <div className="group/vol flex items-center gap-1.5">
      <button
        onClick={toggleMute}
        className="text-slate hover:text-foreground grid h-7 w-7 place-items-center rounded transition-colors duration-150"
        title="Mute (M)"
      >
        {muted || volume === 0 ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
      </button>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={muted ? 0 : volume}
        onChange={(e) => {
          const v = Number(e.target.value);
          setVolume(v);
          setMuted(v === 0);
          if (mediaEl) {
            mediaEl.volume = v;
            mediaEl.muted = v === 0;
          }
        }}
        className="mini-player-scrubber h-1 w-20 cursor-pointer"
        style={
          {
            '--progress': `${(muted ? 0 : volume) * 100}%`,
          } as React.CSSProperties
        }
      />
    </div>
  );

  const RightControls = (
    <>
      {VolumeControl}
      <button
        onClick={onExpand}
        className="text-slate hover:text-foreground grid h-7 w-7 place-items-center rounded transition-colors duration-150"
        title="Expand (F)"
      >
        <Maximize2 className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={onClose}
        className="text-slate hover:bg-rose-500/15 hover:text-rose-400 grid h-7 w-7 place-items-center rounded transition-colors duration-150"
        title="Close (Esc)"
      >
        <X className="h-4 w-4" />
      </button>
    </>
  );

  // ─────────────────────────── audio mode ───────────────────────────

  if (isAudio) {
    return (
      <motion.div
        key={`audio-${file.id}`}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 12 }}
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        className="bg-surface/90 border-hairline pointer-events-auto fixed bottom-3 left-[268px] right-3 z-[150] flex items-center gap-4 rounded-xl border px-3 py-2 shadow-2xl backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Album-art slot */}
        <div className="from-primary/30 to-primary/10 ring-hairline grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-gradient-to-br ring-1">
          <Music2 className="text-primary h-5 w-5" strokeWidth={1.75} />
        </div>

        {/* File metadata */}
        <div className="min-w-0 flex-1 max-w-[28%]">
          <div className="text-foreground truncate text-[13px] font-medium" title={file.name}>
            {file.name}
          </div>
          <div className="text-slate truncate text-[11px]">
            {typeof currentIndex === 'number' &&
            typeof totalItems === 'number' &&
            totalItems > 0
              ? `Track ${currentIndex + 1} of ${totalItems}`
              : 'Streaming from Telegrab'}
          </div>
        </div>

        {/* Center: transport + scrubber */}
        <div className="flex flex-1 max-w-[42rem] flex-col gap-1">
          <div className="flex items-center justify-center gap-2">{Transport}</div>
          {ProgressBar}
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-1.5">{RightControls}</div>

        <audio
          ref={audioRef}
          src={streamUrl ?? undefined}
          autoPlay
          onTimeUpdate={onTimeUpdate}
          onLoadedMetadata={onLoadedMeta}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={onEnded}
        />
      </motion.div>
    );
  }

  // ─────────────────────────── video mode ───────────────────────────

  if (isVideo) {
    return (
      <motion.div
        key={`video-${file.id}`}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.98 }}
        transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
        className="pointer-events-auto fixed bottom-3 right-3 z-[150] w-[480px] max-w-[calc(100vw-1.5rem)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bg-surface/95 border-hairline overflow-hidden rounded-xl border shadow-2xl backdrop-blur-xl">
          {/* Video frame */}
          <div className="relative aspect-video w-full bg-black">
            {!streamUrl ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/70">
                <div className="border-primary/30 border-t-primary h-6 w-6 animate-spin rounded-full border-2" />
                <span className="text-[11px]">Preparing stream…</span>
              </div>
            ) : (
              <video
                ref={videoRef}
                src={streamUrl}
                autoPlay
                playsInline
                onTimeUpdate={onTimeUpdate}
                onLoadedMetadata={onLoadedMeta}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onEnded={onEnded}
                onClick={togglePlay}
                onDoubleClick={onExpand}
                className="h-full w-full object-contain"
              />
            )}

            {/* Top-right pinned actions (expand/close) */}
            <div className="absolute right-2 top-2 flex gap-1">
              <button
                onClick={onExpand}
                className={cn(
                  'grid h-7 w-7 place-items-center rounded-md',
                  'bg-black/50 text-white/80 backdrop-blur-md transition-colors duration-150',
                  'hover:bg-black/70 hover:text-white'
                )}
                title="Expand (F)"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={onClose}
                className={cn(
                  'grid h-7 w-7 place-items-center rounded-md',
                  'bg-black/50 text-white/80 backdrop-blur-md transition-colors duration-150',
                  'hover:bg-rose-500 hover:text-white'
                )}
                title="Close (Esc)"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Prev/Next floating arrows */}
            {(onPrev || onNext) && (
              <>
                {onPrev && (
                  <button
                    onClick={onPrev}
                    className="absolute left-2 top-1/2 -translate-y-1/2 grid h-8 w-8 place-items-center rounded-full bg-black/45 text-white/85 backdrop-blur-md transition-all duration-150 hover:bg-black/70 hover:text-white"
                    title="Previous"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                )}
                {onNext && (
                  <button
                    onClick={onNext}
                    className="absolute right-2 top-1/2 -translate-y-1/2 grid h-8 w-8 place-items-center rounded-full bg-black/45 text-white/85 backdrop-blur-md transition-all duration-150 hover:bg-black/70 hover:text-white"
                    title="Next"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                )}
              </>
            )}
          </div>

          {/* Controls row */}
          <div className="flex flex-col gap-2 px-3 py-2.5">
            <div className="text-foreground truncate text-[12px] font-medium" title={file.name}>
              {file.name}
            </div>
            {ProgressBar}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1">{Transport}</div>
              <div className="flex items-center gap-1.5">{VolumeControl}</div>
            </div>
          </div>
        </div>
      </motion.div>
    );
  }

  return null;
}
