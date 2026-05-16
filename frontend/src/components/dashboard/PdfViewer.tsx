import { useEffect, useState, useRef } from 'react';
import { X, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import { invoke } from '../../lib/platform/core';
// Use the legacy build — the modern build uses Map.getOrInsertComputed()
// which isn't available in Tauri's WebKit WebView
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs';
import { TelegramFile } from '../../types';

// Use Vite's ?url suffix to get a properly bundled asset URL for the worker
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.mjs?url';
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

interface StreamInfo {
  token: string;
  base_url: string;
}

interface PdfViewerProps {
  file: TelegramFile;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  currentIndex?: number;
  totalItems?: number;
  activeFolderId: number | null;
}

export function PdfViewer({
  file,
  onClose,
  onNext,
  onPrev,
  currentIndex,
  totalItems,
  activeFolderId,
}: PdfViewerProps) {
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null);
  const [pdf, setPdf] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState<number>(1.2);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pdfRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null);

  // Fetch stream info once
  useEffect(() => {
    invoke<StreamInfo>('cmd_get_stream_info')
      .then(setStreamInfo)
      .catch((err) => {
        console.error('Failed to get stream info:', err);
        setError('Failed to initialize stream');
      });
  }, []);

  // Load PDF document when stream URL is ready or file changes
  useEffect(() => {
    if (!streamInfo) return;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setPdf(null);
    setNumPages(0);

    const folderIdParam = activeFolderId !== null ? activeFolderId.toString() : 'home';
    const streamUrl = `${streamInfo.base_url}/stream/${folderIdParam}/${file.id}?token=${streamInfo.token}`;

    const loadingTask = pdfjsLib.getDocument(streamUrl);

    loadingTask.promise.then(
      (pdfDoc) => {
        if (cancelled) {
          pdfDoc.destroy();
          return;
        }
        // Destroy previous document if any
        if (pdfRef.current) {
          pdfRef.current.destroy();
        }
        pdfRef.current = pdfDoc;
        setPdf(pdfDoc);
        setNumPages(pdfDoc.numPages);
        setLoading(false);
      },
      (err) => {
        if (cancelled) return;
        console.error('Error loading PDF:', err);
        setError('Failed to load PDF document.');
        setLoading(false);
      }
    );

    return () => {
      cancelled = true;
      loadingTask.destroy();
    };
  }, [streamInfo, activeFolderId, file.id]);

  // Cleanup PDF document on unmount
  useEffect(() => {
    return () => {
      if (pdfRef.current) {
        pdfRef.current.destroy();
        pdfRef.current = null;
      }
    };
  }, []);

  // Keyboard shortcuts
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
        return;
      }

      if (e.key === '=' || key === '+') {
        e.preventDefault();
        setScale((s) => Math.min(s + 0.2, 3));
      }

      if (e.key === '-') {
        e.preventDefault();
        setScale((s) => Math.max(s - 0.2, 0.5));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, onNext, onPrev]);

  const handleZoomIn = (e: React.MouseEvent) => {
    e.stopPropagation();
    setScale((s) => Math.min(s + 0.2, 3));
  };

  const handleZoomOut = (e: React.MouseEvent) => {
    e.stopPropagation();
    setScale((s) => Math.max(s - 0.2, 0.5));
  };

  const handleFitWidth = (e: React.MouseEvent) => {
    e.stopPropagation();
    setScale(1.2);
  };

  return (
    <div
      className="animate-in fade-in fixed inset-0 z-[200] flex flex-col bg-black/90 p-4 backdrop-blur-md duration-200"
      onClick={onClose}
    >
      {/* Header / Controls */}
      <div className="pointer-events-none absolute top-4 right-0 left-0 z-10 flex items-center justify-between px-8">
        <div className="pointer-events-auto rounded-full border border-white/10 bg-black/40 px-4 py-2 text-white backdrop-blur-md">
          <h3 className="max-w-sm truncate px-2 text-sm font-medium">{file.name}</h3>
        </div>

        <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-white/10 bg-black/40 p-1.5 backdrop-blur-md">
          <button
            onClick={handleZoomOut}
            className="rounded-full p-2 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            title="Zoom Out (-)"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="min-w-[3rem] text-center text-xs font-medium text-white/90">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            className="rounded-full p-2 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            title="Zoom In (+)"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <div className="mx-1 h-4 w-px bg-white/20"></div>
          <button
            onClick={handleFitWidth}
            className="rounded-full p-2 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            title="Fit Width"
          >
            <Maximize className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Navigation Buttons */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onPrev?.();
        }}
        className="absolute top-1/2 left-4 z-10 -translate-y-1/2 rounded-full border border-white/10 bg-black/40 p-3 text-white/50 backdrop-blur-md transition-all hover:bg-black/60 hover:text-white"
        title="Previous file (ArrowLeft / J)"
      >
        <ChevronLeft className="h-6 w-6" />
      </button>

      <button
        onClick={(e) => {
          e.stopPropagation();
          onNext?.();
        }}
        className="absolute top-1/2 right-4 z-10 -translate-y-1/2 rounded-full border border-white/10 bg-black/40 p-3 text-white/50 backdrop-blur-md transition-all hover:bg-black/60 hover:text-white"
        title="Next file (ArrowRight / L)"
      >
        <ChevronRight className="h-6 w-6" />
      </button>

      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-10 rounded-full border border-white/10 bg-black/40 p-3 text-white/50 backdrop-blur-md transition-all hover:bg-black/60 hover:text-white"
      >
        <X className="h-6 w-6" />
      </button>

      {/* Scrollable Document Container */}
      <div
        ref={containerRef}
        className="custom-scrollbar relative flex w-full flex-1 flex-col items-center overflow-auto pt-20 pb-8"
        onClick={(e) => e.stopPropagation()}
      >
        {loading && (
          <div className="absolute inset-0 flex flex-1 flex-col items-center justify-center text-white">
            <div className="border-telegram-primary mb-4 h-10 w-10 animate-spin rounded-full border-4 border-t-transparent"></div>
            <p>Loading document...</p>
            <p className="mt-1 text-xs text-white/50">Downloading from Telegram...</p>
          </div>
        )}

        {error && (
          <div className="mt-20 flex flex-col items-center justify-center rounded-xl border border-red-500/50 bg-red-500/20 p-6 text-white">
            <p className="mb-2 font-bold">Error</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {pdf && numPages > 0 && (
          <div className="flex w-full flex-col items-center gap-4">
            {Array.from({ length: numPages }, (_, index) => (
              <PdfPage
                key={`${file.id}_page_${index + 1}`}
                pageNumber={index + 1}
                pdf={pdf}
                scale={scale}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer Navigation Info */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-black/40 px-4 py-1.5 text-sm text-white/50 backdrop-blur-md">
        {typeof currentIndex === 'number' && typeof totalItems === 'number' && totalItems > 0 && (
          <span className="mr-3 border-r border-white/20 pr-3">
            File {currentIndex + 1} of {totalItems}
          </span>
        )}
        <span>
          {numPages} {numPages === 1 ? 'page' : 'pages'}
        </span>
      </div>
    </div>
  );
}

// Individual Page Component — lazy-loaded via IntersectionObserver
function PdfPage({
  pageNumber,
  pdf,
  scale,
}: {
  pageNumber: number;
  pdf: pdfjsLib.PDFDocumentProxy;
  scale: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderTaskRef = useRef<ReturnType<pdfjsLib.PDFPageProxy['render']> | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState<pdfjsLib.PDFPageProxy | null>(null);

  // Intersection Observer — load page data when within 1000px of viewport
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setIsVisible(true);
        }
      },
      { rootMargin: '1000px 0px' }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fetch the PDF page object when visible
  useEffect(() => {
    if (!isVisible || !pdf) return;

    let cancelled = false;
    pdf
      .getPage(pageNumber)
      .then((loadedPage) => {
        if (!cancelled) {
          setPage(loadedPage);
        }
      })
      .catch((err) => console.error(`Error loading page ${pageNumber}:`, err));

    return () => {
      cancelled = true;
    };
  }, [isVisible, pdf, pageNumber]);

  // Render the page to canvas — re-runs when page loads or scale changes
  useEffect(() => {
    if (!page || !canvasRef.current || !isVisible) return;

    const viewport = page.getViewport({ scale });
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');

    if (!context) return;

    // Cancel any in-flight render before starting a new one
    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    // Size canvas and clear before render to avoid stale frame flash
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    context.clearRect(0, 0, viewport.width, viewport.height);

    const renderTask = page.render({
      canvasContext: context,
      viewport: viewport,
      canvas: canvas,
    });
    renderTaskRef.current = renderTask;

    renderTask.promise.catch((err) => {
      // RenderingCancelledException is expected during zoom — ignore it
      if (err?.name !== 'RenderingCancelledException') {
        console.error(`Render error on page ${pageNumber}:`, err);
      }
    });

    return () => {
      renderTask.cancel();
      renderTaskRef.current = null;
    };
  }, [page, scale, isVisible, pageNumber]);

  // Estimated dimensions for the placeholder before page loads (US Letter @ 96 DPI)
  const estimatedHeight = 1056 * scale;
  const estimatedWidth = 816 * scale;

  return (
    <div
      ref={containerRef}
      className="relative my-2 flex flex-col items-center overflow-hidden rounded-lg bg-white/5 shadow-[0_10px_40px_rgba(0,0,0,0.5)] transition-shadow"
      style={{
        minHeight: !page ? `${estimatedHeight}px` : undefined,
        minWidth: !page ? `${estimatedWidth}px` : undefined,
      }}
    >
      <canvas ref={canvasRef} className="h-auto max-w-full bg-white" />

      {!page && isVisible && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-white/30">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white/60"></div>
        </div>
      )}
    </div>
  );
}
