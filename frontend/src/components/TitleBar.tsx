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
        <img src="/icon.png" alt="Telegrab" className="h-5 w-5 rounded-md" />
        <span className="text-ink-deep text-xs font-bold tracking-tight">Telegrab</span>
      </div>

      <div className="flex h-full items-center">
        <button
          onClick={handleMinimize}
          className="text-slate hover:text-foreground flex h-full w-12 items-center justify-center transition-colors duration-150 ease-out hover:bg-white/[0.04] active:bg-white/[0.08]"
          title="Minimize"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          onClick={handleMaximize}
          className="text-slate hover:text-foreground flex h-full w-12 items-center justify-center transition-colors duration-150 ease-out hover:bg-white/[0.04] active:bg-white/[0.08]"
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
          className="text-slate flex h-full w-12 items-center justify-center transition-colors duration-150 ease-out hover:bg-rose-500 hover:text-white active:bg-rose-600"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
