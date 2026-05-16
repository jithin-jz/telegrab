import { Minus, Square, X } from 'lucide-react';
import { invoke } from '../lib/platform/core';

export function TitleBar() {
  const handleMinimize = () => invoke('cmd_window_minimize');
  const handleMaximize = () => invoke('cmd_window_maximize');
  const handleClose = () => invoke('cmd_window_close');

  return (
    <div className="h-8 bg-canvas border-b border-hairline flex items-center justify-between select-none pywebview-drag-region">
      <div className="flex items-center gap-2 px-3 pointer-events-none">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
          <path d="M12 2v8" />
          <path d="m16 6-4 4-4-4" />
          <rect width="20" height="8" x="2" y="14" rx="2" />
        </svg>
        <span className="text-[11px] font-medium text-stone tracking-wide">Telegrab</span>
      </div>
      
      <div className="flex items-center h-full no-drag">
        <button 
          onClick={handleMinimize}
          className="h-full px-3 text-slate hover:bg-white/5 transition-colors flex items-center"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button 
          onClick={handleMaximize}
          className="h-full px-3 text-slate hover:bg-white/5 transition-colors flex items-center"
        >
          <Square className="w-2.5 h-2.5" />
        </button>
        <button 
          onClick={handleClose}
          className="h-full px-3 text-slate hover:bg-rose-500/80 hover:text-white transition-colors flex items-center"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
