import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Unlock, Shield, X } from 'lucide-react';
import { invoke } from '../../lib/platform/core';
import { toast } from 'sonner';

interface VaultModalProps {
  isOpen: boolean;
  onClose: () => void;
  folderId: number;
  folderName: string;
  isVault: boolean;
  isLocked: boolean;
  onUnlocked: () => void;
}

export function VaultModal({
  isOpen,
  onClose,
  folderId,
  folderName,
  isVault,
  isLocked,
  onUnlocked,
}: VaultModalProps) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleUnlock = async () => {
    if (!password) return;
    setLoading(true);
    try {
      await invoke('cmd_unlock_vault', { folderId, password });
      toast.success('Vault unlocked');
      setPassword('');
      onUnlocked();
      onClose();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!password || password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      await invoke('cmd_create_vault', { name: folderName, password, folderId });
      toast.success('Vault created! Files will be encrypted before upload.');
      setPassword('');
      onUnlocked();
      onClose();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[150] flex items-center justify-center bg-black/55 backdrop-blur-[6px]"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="bg-surface border-hairline w-full max-w-sm rounded-xl border p-6 shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="text-primary h-5 w-5" />
              <h3 className="text-foreground font-semibold">
                {isVault ? (isLocked ? 'Unlock Vault' : 'Vault Unlocked') : 'Create Vault'}
              </h3>
            </div>
            <button onClick={onClose} className="text-slate hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          <p className="text-slate mb-4 text-sm">
            {isVault
              ? 'Enter your password to access encrypted files.'
              : 'Protect this folder with AES-256 encryption. Files will be encrypted before upload.'}
          </p>

          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (isVault ? handleUnlock() : handleCreate())}
            placeholder={isVault ? 'Vault password' : 'Choose a strong password (8+ chars)'}
            className="bg-surface-soft border-hairline text-foreground placeholder:text-slate mb-4 w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:border-primary"
            autoFocus
          />

          <button
            onClick={isVault ? handleUnlock : handleCreate}
            disabled={loading || !password}
            className="bg-primary hover:bg-primary/90 flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50"
          >
            {isVault ? (
              <>
                <Unlock className="h-4 w-4" /> {loading ? 'Unlocking...' : 'Unlock'}
              </>
            ) : (
              <>
                <Lock className="h-4 w-4" /> {loading ? 'Creating...' : 'Create Vault'}
              </>
            )}
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
