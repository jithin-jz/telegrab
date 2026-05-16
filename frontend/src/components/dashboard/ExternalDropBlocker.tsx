import { useState, useEffect } from 'react';
import { Upload } from 'lucide-react';

/**
 * ExternalDropBlocker - Intercepts external file drops and shows a helpful message
 *
 * Since Tauri's native drag-drop is disabled, we need to prevent the browser's
 * default behavior (which would show file contents) and instead guide users
 * to use the Upload button.
 */
export function ExternalDropBlocker({ onUploadClick }: { onUploadClick: () => void }) {
  const [showMessage, setShowMessage] = useState(false);

  useEffect(() => {
    let hideTimeout: ReturnType<typeof setTimeout>;

    const handleDragOver = (e: DragEvent) => {
      // Check if this is an external file drag (from Finder)
      if (e.dataTransfer?.types.includes('Files')) {
        e.preventDefault();
        e.stopPropagation();
        setShowMessage(true);
        clearTimeout(hideTimeout);
      }
    };

    const handleDragLeave = (e: DragEvent) => {
      // Only hide if leaving the window entirely
      if (
        e.clientX <= 0 ||
        e.clientY <= 0 ||
        e.clientX >= window.innerWidth ||
        e.clientY >= window.innerHeight
      ) {
        hideTimeout = setTimeout(() => setShowMessage(false), 100);
      }
    };

    const handleDrop = (e: DragEvent) => {
      // Block external file drops
      if (e.dataTransfer?.types.includes('Files')) {
        e.preventDefault();
        e.stopPropagation();
        // Keep message visible briefly so user sees it
        setTimeout(() => setShowMessage(false), 2000);
      }
    };

    document.addEventListener('dragover', handleDragOver, true);
    document.addEventListener('dragleave', handleDragLeave, true);
    document.addEventListener('drop', handleDrop, true);

    return () => {
      document.removeEventListener('dragover', handleDragOver, true);
      document.removeEventListener('dragleave', handleDragLeave, true);
      document.removeEventListener('drop', handleDrop, true);
      clearTimeout(hideTimeout);
    };
  }, []);

  if (!showMessage) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass bg-telegram-surface border-telegram-border pointer-events-auto mx-4 max-w-md rounded-2xl border p-8 shadow-2xl">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="bg-telegram-primary/20 flex h-16 w-16 items-center justify-center rounded-full">
            <Upload className="text-telegram-primary h-8 w-8" />
          </div>
          <div>
            <h3 className="text-telegram-text mb-2 text-lg font-semibold">Use the Upload Button</h3>
            <p className="text-telegram-subtext text-sm">
              To upload files, please use the <strong>Upload</strong> button in the toolbar.
              <br />
              <span className="mt-2 block text-xs opacity-70">
                Drag-and-drop from Finder is not supported.
              </span>
            </p>
          </div>
          <button
            onClick={() => {
              setShowMessage(false);
              onUploadClick();
            }}
            className="bg-telegram-primary hover:bg-telegram-primary/90 mt-2 rounded-lg px-6 py-2 font-medium text-white transition-colors"
          >
            Open Upload Dialog
          </button>
        </div>
      </div>
    </div>
  );
}
