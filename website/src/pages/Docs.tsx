import { motion } from 'framer-motion'

function CodeBlock({ children, title }: { children: string; title?: string }) {
  return (
    <div className="rounded-[8px] border border-hairline-dark overflow-hidden">
      {title && (
        <div className="border-b border-hairline-dark px-4 py-2 bg-canvas-soft">
          <span className="text-[12px] font-bold uppercase tracking-[0.96px] text-on-primary-mute">{title}</span>
        </div>
      )}
      <pre className="p-4 overflow-x-auto bg-canvas">
        <code className="text-[14px] text-on-primary-mute leading-[1.7] font-mono">{children}</code>
      </pre>
    </div>
  )
}

export function Docs() {
  return (
    <>
      {/* Header */}
      <section className="bg-canvas pt-16 pb-16">
        <div className="mx-auto max-w-[680px] px-8 text-center">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="font-display text-[60px] font-bold uppercase leading-[1.2] tracking-[1.2px] text-on-primary max-[768px]:text-[40px]">
              INSTALLATION
            </h1>
            <p className="mt-4 text-[16px] leading-[1.7] tracking-[0.32px] text-on-primary-mute">
              Get Telegrab running in under 5 minutes.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Content */}
      <section className="bg-canvas-soft border-t border-hairline-dark">
        <div className="mx-auto max-w-[680px] px-8 py-16 space-y-16">

          <Step title="System Requirements">
            <div className="grid gap-8 sm:grid-cols-2">
              <div>
                <p className="text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary">Windows</p>
                <ul className="mt-2 text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px] space-y-1">
                  <li>Windows 10/11 (64-bit)</li>
                  <li>WebView2 Runtime (included in Win 11)</li>
                </ul>
              </div>
              <div>
                <p className="text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary">macOS</p>
                <ul className="mt-2 text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px] space-y-1">
                  <li>macOS 10.15 (Catalina) or later</li>
                  <li>Apple Silicon or Intel</li>
                </ul>
              </div>
            </div>
          </Step>

          <Step title="01 — Download & Install">
            <p className="text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
              Download the latest installer from GitHub Releases:
            </p>
            <div className="mt-4 space-y-3">
              <CodeBlock title="Windows">{`# Download the Setup installer from:
https://github.com/jithin-jz/telegrab/releases/latest

# Run the installer
Telegrab-Setup.exe`}</CodeBlock>
              <CodeBlock title="macOS">{`# Download the .dmg or .zip from:
https://github.com/jithin-jz/telegrab/releases/latest

# Drag Telegrab.app to Applications`}</CodeBlock>
            </div>
          </Step>

          <Step title="02 — Get Telegram API Keys">
            <p className="text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
              You need your own Telegram API credentials. This is a one-time setup:
            </p>
            <ol className="mt-4 list-decimal list-inside space-y-2 text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
              <li>Visit <a href="https://my.telegram.org" target="_blank" rel="noopener noreferrer" className="text-on-primary underline">my.telegram.org</a></li>
              <li>Log in with your phone number</li>
              <li>Go to <strong className="text-on-primary font-bold">API development tools</strong></li>
              <li>Create a new application</li>
              <li>Copy your <strong className="text-on-primary font-bold">API ID</strong> and <strong className="text-on-primary font-bold">API Hash</strong></li>
            </ol>
          </Step>

          <Step title="03 — Sign In">
            <p className="text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
              Launch Telegrab and enter your API credentials. Then sign in using:
            </p>
            <ul className="mt-4 list-disc list-inside space-y-2 text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
              <li><strong className="text-on-primary font-bold">QR Code</strong> — Scan with your Telegram mobile app</li>
              <li><strong className="text-on-primary font-bold">Phone Number</strong> — Enter your number and the verification code</li>
            </ul>
          </Step>

          <Step title="04 — Start Using">
            <p className="text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
              You're all set. Telegrab shows your Saved Messages as the default storage.
              Create folders, upload files via drag & drop, and stream media directly.
            </p>
            <div className="mt-4 border border-hairline-dark rounded-[8px] p-6">
              <p className="text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary">Tips</p>
              <ul className="mt-3 space-y-2 text-[16px] text-on-primary-mute leading-[1.7] tracking-[0.32px]">
                <li>Use <kbd className="rounded-[4px] border border-hairline-dark bg-canvas px-2 py-0.5 text-[12px] font-mono text-on-primary">Ctrl+K</kbd> to open the command palette</li>
                <li>Drag files directly into the window to upload</li>
                <li>Right-click files for context menu options</li>
                <li>Enable the REST API in Settings for automation</li>
              </ul>
            </div>
          </Step>

          <Step title="Uninstall">
            <div className="space-y-3">
              <CodeBlock title="Windows">{`# Via Settings
Settings → Apps → Installed apps → Telegrab → Uninstall`}</CodeBlock>
              <CodeBlock title="macOS">{`# Drag to Trash
Move Telegrab.app from Applications to Trash`}</CodeBlock>
            </div>
          </Step>

        </div>
      </section>
    </>
  )
}

function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="border-t border-hairline-dark pt-8"
    >
      <h2 className="font-display text-[48px] font-bold uppercase leading-[1.25] tracking-[0.96px] text-on-primary max-[768px]:text-[28px]">{title}</h2>
      <div className="mt-6">{children}</div>
    </motion.div>
  )
}
