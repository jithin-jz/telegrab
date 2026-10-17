import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Unlock, Shield, X, ShieldOff } from 'lucide-react';
import { invoke, errorMessage } from '../../lib/platform/core';
import { toast } from 'sonner';
import { useConfirm } from '../../contexts/ConfirmContext';

export interface VaultStatus {
  is_vault: boolean;
  locked: boolean;
}

interface VaultModalProps {
  isOpen: boolean;
  onClose: () => void;
  folderId: number;
  folderName: string;
  status: VaultStatus;
  onChanged: () => void;
}

const MIN_PASSWORD = 8;

export function VaultModal({ isOpen, onClose, folderId, folderName, status, onChanged }: VaultModalProps) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { confirm } = useConfirm();

  const mode: 'create' | 'unlock' | 'manage' = !status.is_vault
    ? 'create'
    : status.locked
      ? 'unlock'
      : 'manage';

  useEffect(() => {
    if (!isOpen) {
      setPassword('');
      setConfirmPassword('');
    }
  }, [isOpen]);

  const run = async (action: () => Promise<void>) => {
    setLoading(true);
    try {
      await action();
      setPassword('');
      setConfirmPassword('');
      onChanged();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const handleUnlock = () =>
    run(async () => {
      await invoke('cmd_unlock_vault', { folderId, password });
      toast.success('Vault unlocked');
      onClose();
    });

  const handleCreate = () => {
    if (password.length < MIN_PASSWORD) {
      toast.error(`Password must be at least ${MIN_PASSWORD} characters`);
      return;
    }
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    return run(async () => {
      await invoke('cmd_create_vault', { name: folderName, password, folderId });
      toast.success('Vault created. New uploads to this folder are encrypted.');
      onClose();
    });
  };

  const handleLock = () =>
    run(async () => {
      await invoke('cmd_lock_vault', { folderId });
      toast.success('Vault locked');
      onClose();
    });

  const handleRemove = async () => {
    const ok = await confirm({
      title: 'Remove vault?',
      message:
        `Files already uploaded to "${folderName}" stay encrypted on Telegram and can NEVER be decrypted again ` +
        'after the vault is removed. Download anything you need first. New uploads will not be encrypted.',
      confirmText: 'Remove vault',
      variant: 'danger',
    });
    if (!ok) return;
    await run(async () => {
      await invoke('cmd_delete_vault', { folderId });
      toast.success('Vault removed');
      onClose();
    });
  };

  const submit = mode === 'create' ? handleCreate : mode === 'unlock' ? handleUnlock : undefined;
  const inputClass =
    'bg-surface-soft border-hairline text-foreground placeholder:text-slate mb-3 w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:border-primary';

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[150] flex items-center justify-center bg-black/55 backdrop-blur-[6px]"
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="vault-modal-title"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-surface border-hairline w-full max-w-sm rounded-xl border p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === 'Escape' && onClose()}
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="text-primary h-5 w-5" />
                <h3 id="vault-modal-title" className="text-foreground font-semibold">
                  {mode === 'create' ? 'Create Vault' : mode === 'unlock' ? 'Unlock Vault' : 'Vault'}
                </h3>
              </div>
              <button onClick={onClose} aria-label="Close" className="text-slate hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-slate mb-4 text-sm">
              {mode === 'create' &&
                'Encrypt everything you upload to this folder with AES-256 before it leaves your device. ' +
                  "There is no password recovery — if you forget it, the files can't be decrypted."}
              {mode === 'unlock' && `Enter the password for "${folderName}" to upload, download and preview files.`}
              {mode === 'manage' && `"${folderName}" is unlocked. It locks automatically after 30 minutes of inactivity.`}
            </p>

            {mode !== 'manage' && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  submit?.();
                }}
              >
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === 'unlock' ? 'Vault password' : `Choose a strong password (${MIN_PASSWORD}+ chars)`}
                  aria-label="Vault password"
                  className={inputClass}
                  autoFocus
                />
                {mode === 'create' && (
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    aria-label="Repeat vault password"
                    className={inputClass}
                  />
                )}
                <button
                  type="submit"
                  disabled={loading || !password}
                  className="bg-primary hover:bg-primary/90 mt-1 flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50"
                >
                  {mode === 'unlock' ? (
                    <>
                      <Unlock className="h-4 w-4" /> {loading ? 'Unlocking...' : 'Unlock'}
                    </>
                  ) : (
                    <>
                      <Lock className="h-4 w-4" /> {loading ? 'Creating...' : 'Create Vault'}
                    </>
                  )}
                </button>
              </form>
            )}

            {mode === 'manage' && (
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleLock}
                  disabled={loading}
                  className="bg-primary hover:bg-primary/90 flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50"
                >
                  <Lock className="h-4 w-4" /> Lock now
                </button>
                <button
                  onClick={handleRemove}
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-rose-400 transition-colors hover:bg-rose-500/10 disabled:opacity-50"
                >
                  <ShieldOff className="h-4 w-4" /> Remove vault
                </button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
