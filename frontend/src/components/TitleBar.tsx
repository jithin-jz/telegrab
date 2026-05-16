import { Minus, Square, X, Copy } from 'lucide-react';
import { useState, useEffect } from 'react';
import { listen } from '../lib/platform/event';

export function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false);

  const handleMinimize = () => {
    // Add a tiny delay to let the UI react if needed, though OS handles most of it
    (window as any).pywebview?.api?.cmd_window_minimize();
  };
  const handleMaximize = () => {
    if (isMaximized) {
      (window as any).pywebview?.api?.cmd_window_restore();
    } else {
      (window as any).pywebview?.api?.cmd_window_maximize();
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
  const handleClose = () => (window as any).pywebview?.api?.cmd_window_close();

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag if left button and not clicking a button
    if (e.button === 0 && !(e.target as HTMLElement).closest('button')) {
      (window as any).pywebview?.drag();
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
        <div className="flex h-5 w-5 items-center justify-center rounded-md bg-primary/10">
          <svg
            width="14"
            height="14"
            viewBox="0 0 512 512"
            fill="currentColor"
            className="text-primary"
          >
            <path d="M512 256C512 114.62 397.38 0 256 0S0 114.62 0 256s114.62 256 256 256 256-114.62 256-256zm-396.12-2.7c74.63-32.52 124.39-53.95 149.29-64.31 71.1-29.57 85.87-34.71 95.5-34.88 2.12-.03 6.85.49 9.92 2.98 2.59 2.1 3.3 4.94 3.64 6.93.34 2 .77 6.53.43 10.08-3.85 40.48-20.52 138.71-29 184.05-3.59 19.19-10.66 25.62-17.5 26.25-14.86 1.37-26.15-9.83-40.55-19.27-22.53-14.76-35.26-23.96-57.13-38.37-25.28-16.66-8.89-25.81 5.51-40.77 3.77-3.92 69.27-63.5 70.54-68.9.16-.68.31-3.2-1.19-4.53s-3.71-.87-5.3-.51c-2.26.51-38.25 24.3-107.98 71.37-10.22 7.02-19.48 10.43-27.77 10.26-9.14-.2-26.72-5.17-39.79-9.42-16.03-5.21-28.77-7.97-27.66-16.82.57-4.61 6.92-9.32 19.04-14.14z" />
          </svg>
        </div>
        <span className="text-ink-deep text-xs font-bold tracking-tight">Telegrab</span>
      </div>

      <div className="flex h-full items-center">
        <button
          onClick={handleMinimize}
          className="text-slate flex h-full w-12 items-center justify-center transition-colors hover:bg-white/5 active:bg-white/10"
          title="Minimize"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          onClick={handleMaximize}
          className="text-slate flex h-full w-12 items-center justify-center transition-colors hover:bg-white/5 active:bg-white/10"
          title={isMaximized ? "Restore" : "Maximize"}
        >
          {isMaximized ? (
            <Copy className="h-3 w-3 rotate-180" />
          ) : (
            <Square className="h-3 w-3" />
          )}
        </button>
        <button
          onClick={handleClose}
          className="text-slate flex h-full w-12 items-center justify-center transition-colors hover:bg-rose-500 hover:text-white active:bg-rose-600"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
