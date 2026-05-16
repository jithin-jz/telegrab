import { FileUp, UploadCloud } from 'lucide-react';

interface EmptyStateProps {
  onUpload: () => void;
}

export function EmptyState({ onUpload }: EmptyStateProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-8 py-16 text-center">
      <div className="relative mb-7 h-32 w-44">
        <div className="border-hairline bg-surface absolute top-4 left-5 h-24 w-32 rounded-lg border shadow-2xl" />
        <div className="border-hairline-strong bg-card absolute top-8 left-2 h-24 w-36 rounded-lg border shadow-2xl" />
        <div className="border-primary/25 bg-primary/10 absolute top-0 right-2 grid h-16 w-12 place-items-center rounded-md border">
          <FileUp className="text-primary h-5 w-5" />
        </div>
        <div className="border-primary/25 bg-primary/10 absolute bottom-0 left-1/2 grid h-16 w-16 -translate-x-1/2 place-items-center rounded-xl border shadow-[0_12px_40px_rgba(124,92,255,0.20)]">
          <UploadCloud className="text-primary h-7 w-7" />
        </div>
      </div>

      <h3 className="text-foreground mb-2 text-xl font-semibold">This folder is empty</h3>
      <p className="text-slate mb-6 max-w-sm text-sm leading-6">
        Start with an upload or drop files anywhere in this window.
      </p>

      <button
        onClick={onUpload}
        className="bg-primary text-on-primary shadow-primary/15 inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium shadow-lg transition-colors hover:brightness-110"
      >
        <UploadCloud className="h-4 w-4" />
        Upload files
      </button>

      <p className="text-slate/50 mt-5 text-xs">
        Tip: use <kbd className="bg-surface-soft text-slate rounded px-1.5 py-0.5">Ctrl + F</kbd> to
        search
      </p>
    </div>
  );
}
