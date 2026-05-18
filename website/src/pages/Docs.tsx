import { motion } from 'framer-motion'
import { Download, Terminal, Key, LogIn, Monitor } from 'lucide-react'

function CodeBlock({ children, title }: { children: string; title?: string }) {
  return (
    <div className="rounded-xl border border-white/5 bg-elevated overflow-hidden">
      {title && (
        <div className="border-b border-white/5 px-4 py-2 bg-surface/50">
          <span className="text-xs font-medium text-slate">{title}</span>
        </div>
      )}
      <pre className="p-4 overflow-x-auto">
        <code className="text-sm text-ink-muted">{children}</code>
      </pre>
    </div>
  )
}

const steps = [
  {
    icon: Download,
    title: '1. Download & Install',
    content: (
      <div className="space-y-4">
        <p className="text-ink-muted text-sm leading-relaxed">
          Download the latest installer from GitHub Releases, or use winget on Windows:
        </p>
        <CodeBlock title="Windows (winget)">
{`winget install jithin-jz.telegrab`}
        </CodeBlock>
        <CodeBlock title="Windows (manual)">
{`# Download from GitHub Releases
https://github.com/jithin-jz/telegrab/releases/latest

# Run the installer
Telegrab-1.4.0-Setup.exe`}
        </CodeBlock>
        <CodeBlock title="macOS">
{`# Download the .dmg from GitHub Releases
https://github.com/jithin-jz/telegrab/releases/latest

# Or download and unzip
unzip telegrab-macos.zip
# Drag Telegrab.app to Applications`}
        </CodeBlock>
      </div>
    ),
  },
  {
    icon: Key,
    title: '2. Get Telegram API Keys',
    content: (
      <div className="space-y-4">
        <p className="text-ink-muted text-sm leading-relaxed">
          You need your own Telegram API credentials. This is a one-time setup:
        </p>
        <ol className="list-decimal list-inside space-y-2 text-sm text-ink-muted">
          <li>Visit <a href="https://my.telegram.org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">my.telegram.org</a></li>
          <li>Log in with your phone number</li>
          <li>Go to <strong className="text-ink">API development tools</strong></li>
          <li>Create a new application (any name/description works)</li>
          <li>Copy your <strong className="text-ink">API ID</strong> and <strong className="text-ink">API Hash</strong></li>
        </ol>
      </div>
    ),
  },
  {
    icon: LogIn,
    title: '3. Sign In',
    content: (
      <div className="space-y-4">
        <p className="text-ink-muted text-sm leading-relaxed">
          Launch Telegrab and enter your API credentials. Then sign in using:
        </p>
        <ul className="list-disc list-inside space-y-2 text-sm text-ink-muted">
          <li><strong className="text-ink">QR Code</strong> — Scan with your Telegram mobile app</li>
          <li><strong className="text-ink">Phone Number</strong> — Enter your number and the verification code</li>
        </ul>
      </div>
    ),
  },
  {
    icon: Monitor,
    title: '4. Start Using',
    content: (
      <div className="space-y-4">
        <p className="text-ink-muted text-sm leading-relaxed">
          You're all set! Telegrab will show your Saved Messages as the default storage.
          Create folders, upload files via drag & drop, and stream media directly.
        </p>
        <div className="rounded-xl border border-white/5 bg-surface/50 p-4">
          <h4 className="text-sm font-semibold mb-2">Tips</h4>
          <ul className="list-disc list-inside space-y-1 text-xs text-ink-muted">
            <li>Use <kbd className="rounded bg-elevated px-1.5 py-0.5 text-[10px] font-mono border border-white/10">Ctrl+K</kbd> to open the command palette</li>
            <li>Drag files directly into the window to upload</li>
            <li>Right-click files for context menu options</li>
            <li>Enable the REST API in Settings for automation</li>
          </ul>
        </div>
      </div>
    ),
  },
]

export function Docs() {
  return (
    <section className="mx-auto max-w-3xl px-6 py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-4xl font-bold tracking-tight">Installation Guide</h1>
        <p className="mt-3 text-ink-muted text-lg">Get Telegrab running in under 5 minutes.</p>
      </motion.div>

      {/* System Requirements */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mt-12 rounded-2xl border border-white/5 bg-surface/50 p-6"
      >
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Terminal className="h-5 w-5 text-primary" />
          System Requirements
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-medium">Windows</h3>
            <ul className="mt-1 text-xs text-ink-muted space-y-1">
              <li>• Windows 10/11 (64-bit)</li>
              <li>• WebView2 Runtime (included in Win 11)</li>
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-medium">macOS</h3>
            <ul className="mt-1 text-xs text-ink-muted space-y-1">
              <li>• macOS 10.15 (Catalina) or later</li>
              <li>• Apple Silicon or Intel</li>
            </ul>
          </div>
        </div>
      </motion.div>

      {/* Steps */}
      <div className="mt-12 space-y-8">
        {steps.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.05 }}
            className="rounded-2xl border border-white/5 bg-surface/30 p-6"
          >
            <h2 className="text-lg font-semibold flex items-center gap-3">
              <div className="rounded-lg bg-primary/10 p-2">
                <step.icon className="h-4 w-4 text-primary" />
              </div>
              {step.title}
            </h2>
            <div className="mt-4">{step.content}</div>
          </motion.div>
        ))}
      </div>

      {/* Uninstall */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="mt-12 rounded-2xl border border-white/5 bg-surface/30 p-6"
      >
        <h2 className="text-lg font-semibold">Uninstall</h2>
        <div className="mt-3 space-y-3">
          <CodeBlock title="Windows">
{`# Via Settings
Settings → Apps → Installed apps → Telegrab → Uninstall

# Via winget
winget uninstall jithin-jz.telegrab`}
          </CodeBlock>
          <CodeBlock title="macOS">
{`# Drag to Trash
Move Telegrab.app from Applications to Trash`}
          </CodeBlock>
        </div>
      </motion.div>
    </section>
  )
}
