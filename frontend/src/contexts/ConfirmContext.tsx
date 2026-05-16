import { createContext, useContext, useState, ReactNode } from 'react';

interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'info';
}

interface ConfirmContextType {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextType | undefined>(undefined);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<ConfirmOptions>({ title: '', message: '' });
  const [resolveRef, setResolveRef] = useState<((value: boolean) => void) | null>(null);

  const confirm = (opts: ConfirmOptions) => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise<boolean>((resolve) => {
      setResolveRef(() => resolve);
    });
  };

  const handleConfirm = () => {
    setIsOpen(false);
    if (resolveRef) resolveRef(true);
  };

  const handleCancel = () => {
    setIsOpen(false);
    if (resolveRef) resolveRef(false);
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {isOpen && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div
            className="bg-surface border-hairline animate-in zoom-in-95 w-96 rounded-xl border p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-foreground mb-2 text-lg font-medium">{options.title}</h3>
            <p className="text-slate mb-6 text-sm whitespace-pre-line">{options.message}</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleCancel}
                className="hover:bg-surface-soft text-slate rounded-lg px-4 py-2 text-sm font-medium transition"
              >
                {options.cancelText || 'Cancel'}
              </button>
              <button
                onClick={handleConfirm}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${options.variant === 'danger' ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20' : 'bg-primary text-on-primary hover:brightness-110'}`}
              >
                {options.confirmText || 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export const useConfirm = () => {
  const context = useContext(ConfirmContext);
  if (!context) throw new Error('useConfirm must be used within a ConfirmProvider');
  return context;
};
