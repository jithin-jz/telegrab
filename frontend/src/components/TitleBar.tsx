import { Minus, Square, X, Copy } from 'lucide-react';
import { useState, useEffect } from 'react';
import { listen } from '../lib/platform/event';
import { invoke } from '../lib/platform/core';

export function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false);

  const handleMinimize = () => {
    invoke('cmd_window_minimize').catch(() => {});
  };
  const handleMaximize = () => {
    if (isMaximized) {
      invoke('cmd_window_restore').catch(() => {});
    } else {
      invoke('cmd_window_maximize').catch(() => {});
    }
  };

  useEffect(() => {
    let unlisten: (() => void) | undefined;

    const setup = async () => {
      unlisten = await listen<boolean>('window-maximized', (event) => {
        setIsMaximized(event.payload);
      });
    };

    setup();
    return () => {
      unlisten?.();
    };
  }, []);
  const handleClose = () => {
    invoke('cmd_window_close').catch(() => {});
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag if left button and not clicking a button
    if (e.button === 0 && !(e.target as HTMLElement).closest('button')) {
      (window as unknown as { pywebview?: { drag?: () => void } }).pywebview?.drag?.();
    }
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    // Only maximize if clicking the title bar background, not buttons
    if (e.target === e.currentTarget) {
      handleMaximize();
    }
  };

  return (
    <header 
      className="bg-canvas border-hairline flex h-10 items-center justify-between border-b select-none z-[100]"
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
    >
      <div className="pointer-events-none flex items-center gap-2 px-3">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" className="h-5 w-5 rounded-md">
          <rect width="512" height="512" rx="96" fill="#6366f1"/>
          <path d="M160 200h192M256 200v160" stroke="#fff" strokeWidth="48" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
          <path d="M200 260l56-56 56 56" stroke="#fff" strokeWidth="36" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0.7"/>
        </svg>
        <span className="text-ink-deep text-xs font-bold tracking-tight">Telegrab</span>
      </div>

      <div className="flex h-full items-center">
        <button
          onClick={handleMinimize}
          className="text-slate hover:text-foreground flex h-full w-12 items-center justify-center transition-colors duration-150 ease-out hover:bg-white/[0.04] active:bg-white/[0.08]"
          aria-label="Minimize window"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          onClick={handleMaximize}
          className="text-slate hover:text-foreground flex h-full w-12 items-center justify-center transition-colors duration-150 ease-out hover:bg-white/[0.04] active:bg-white/[0.08]"
          aria-label={isMaximized ? "Restore window" : "Maximize window"}
        >
          {isMaximized ? (
            <Copy className="h-3 w-3 rotate-180" />
          ) : (
            <Square className="h-3 w-3" />
          )}
        </button>
        <button
          onClick={handleClose}
          className="text-slate flex h-full w-12 items-center justify-center transition-colors duration-150 ease-out hover:bg-rose-500 hover:text-white active:bg-rose-600"
          aria-label="Close window"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
