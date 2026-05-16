import { FileUp, UploadCloud } from 'lucide-react';

interface EmptyStateProps {
    onUpload: () => void;
}

export function EmptyState({ onUpload }: EmptyStateProps) {
    return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center px-8 py-16 text-center">
            <div className="relative mb-7 h-32 w-44">
                <div className="absolute left-5 top-4 h-24 w-32 rounded-lg border border-hairline bg-surface shadow-2xl" />
                <div className="absolute left-2 top-8 h-24 w-36 rounded-lg border border-hairline-strong bg-card shadow-2xl" />
                <div className="absolute right-2 top-0 h-16 w-12 rounded-md border border-primary/25 bg-primary/10 grid place-items-center">
                    <FileUp className="h-5 w-5 text-primary" />
                </div>
                <div className="absolute bottom-0 left-1/2 grid h-16 w-16 -translate-x-1/2 place-items-center rounded-xl border border-primary/25 bg-primary/10 shadow-[0_12px_40px_rgba(124,92,255,0.20)]">
                    <UploadCloud className="h-7 w-7 text-primary" />
                </div>
            </div>

            <h3 className="mb-2 text-xl font-semibold text-foreground">
                This folder is empty
            </h3>
            <p className="mb-6 max-w-sm text-sm leading-6 text-slate">
                Start with an upload or drop files anywhere in this window.
            </p>

            <button
                onClick={onUpload}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-on-primary shadow-lg shadow-primary/15 transition-colors hover:brightness-110"
            >
                <UploadCloud className="h-4 w-4" />
                Upload files
            </button>

            <p className="mt-5 text-xs text-slate/50">
                Tip: use <kbd className="rounded bg-surface-soft px-1.5 py-0.5 text-slate">Ctrl + F</kbd> to search
            </p>
        </div>
    );
}
