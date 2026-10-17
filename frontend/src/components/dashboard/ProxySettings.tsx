import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { invoke, errorMessage } from '../../lib/platform/core';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';

type ProxyType = 'socks5' | 'socks4' | 'http' | 'mtproxy';

interface ProxyConfig {
  enabled: boolean;
  type: ProxyType;
  host: string;
  port: number | '';
  username: string;
  has_password?: boolean;
  has_secret?: boolean;
}

const TYPES: { value: ProxyType; label: string }[] = [
  { value: 'socks5', label: 'SOCKS5' },
  { value: 'socks4', label: 'SOCKS4' },
  { value: 'http', label: 'HTTP' },
  { value: 'mtproxy', label: 'MTProxy' },
];

const field =
  'bg-surface-soft border-hairline text-foreground placeholder:text-slate w-full rounded-lg border px-3 py-2 text-[12px] outline-none focus:border-primary';

/**
 * Proxy configuration. Secrets (password / MTProxy secret) are write-only:
 * the backend reports whether one is saved, and leaving the field empty
 * keeps the saved value.
 */
export function ProxySettings() {
  const [cfg, setCfg] = useState<ProxyConfig | null>(null);
  const [password, setPassword] = useState('');
  const [secret, setSecret] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    invoke<ProxyConfig>('cmd_get_proxy')
      .then(setCfg)
      .catch(() => setCfg({ enabled: false, type: 'socks5', host: '', port: '', username: '' }));
  }, []);

  if (!cfg) return <p className="text-slate text-[12px]">Loading…</p>;

  const update = <K extends keyof ProxyConfig>(key: K, value: ProxyConfig[K]) =>
    setCfg((c) => (c ? { ...c, [key]: value } : c));

  const save = async () => {
    setSaving(true);
    try {
      await invoke('cmd_set_proxy', {
        enabled: cfg.enabled,
        type: cfg.type,
        host: cfg.host,
        port: cfg.port === '' ? 0 : cfg.port,
        username: cfg.username,
        password,
        secret,
      });
      setPassword('');
      setSecret('');
      toast.success(cfg.enabled ? 'Proxy saved — reconnected through it' : 'Proxy disabled — reconnected');
      setCfg(await invoke<ProxyConfig>('cmd_get_proxy'));
    } catch (e) {
      toast.error(`Proxy not saved: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const isMtproxy = cfg.type === 'mtproxy';

  return (
    <div className="space-y-4 py-1">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-foreground text-[13px] font-medium">Use a proxy</p>
          <p className="text-slate mt-0.5 text-[11px] leading-tight">
            Connect to Telegram through a proxy, e.g. where Telegram is blocked
          </p>
        </div>
        <Switch checked={cfg.enabled} onCheckedChange={(v) => update('enabled', v)} />
      </div>

      <fieldset disabled={!cfg.enabled} className="space-y-3 disabled:opacity-50">
        <div className="border-hairline inline-flex rounded-lg border bg-surface-soft p-0.5">
          {TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => update('type', t.value)}
              className={`rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-all ${
                cfg.type === t.value
                  ? 'bg-surface text-foreground border-hairline border shadow-sm'
                  : 'text-slate hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <input
            className={field}
            placeholder="Host"
            aria-label="Proxy host"
            value={cfg.host}
            onChange={(e) => update('host', e.target.value)}
          />
          <input
            className={`${field} w-28`}
            placeholder="Port"
            aria-label="Proxy port"
            inputMode="numeric"
            value={cfg.port}
            onChange={(e) => {
              const n = e.target.value.replace(/\D/g, '');
              update('port', n === '' ? '' : Number(n));
            }}
          />
        </div>

        {isMtproxy ? (
          <input
            className={field}
            type="password"
            aria-label="MTProxy secret"
            placeholder={cfg.has_secret ? 'Secret (saved — leave empty to keep)' : 'Secret'}
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
          />
        ) : (
          <div className="flex gap-2">
            <input
              className={field}
              placeholder="Username (optional)"
              aria-label="Proxy username"
              value={cfg.username}
              onChange={(e) => update('username', e.target.value)}
            />
            <input
              className={field}
              type="password"
              aria-label="Proxy password"
              placeholder={cfg.has_password ? 'Password (saved)' : 'Password (optional)'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
        )}
      </fieldset>

      <Button size="sm" onClick={save} disabled={saving} className="h-8 text-xs">
        {saving ? 'Reconnecting…' : 'Save & reconnect'}
      </Button>
    </div>
  );
}
