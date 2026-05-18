import { motion } from 'framer-motion'

function CodeBlock({ children, title }: { children: string; title?: string }) {
  return (
    <div className="rounded-[8px] border border-hairline bg-parchment overflow-hidden">
      {title && (
        <div className="border-b border-hairline px-4 py-2">
          <span className="text-[12px] font-semibold text-ink-subtle tracking-[-0.12px]">{title}</span>
        </div>
      )}
      <pre className="p-4 overflow-x-auto">
        <code className="text-[14px] text-ink-muted leading-[1.43] tracking-[-0.224px] font-mono">{children}</code>
      </pre>
    </div>
  )
}

export function Docs() {
  return (
    <>
      {/* Header — parchment */}
      <section className="bg-parchment">
        <div className="mx-auto max-w-[680px] px-6 py-20 text-center">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="font-display text-[40px] font-semibold leading-[1.1] text-ink">
              Installation Guide
            </h1>
            <p className="mt-2 text-[21px] font-normal leading-[1.19] tracking-[0.231px] text-ink-subtle">
              Get Telegrab running in under 5 minutes.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Content — white */}
      <section className="bg-canvas">
        <div className="mx-auto max-w-[680px] px-6 py-16 space-y-12">

          {/* Requirements */}
          <Step title="System Requirements">
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <p className="text-[14px] font-semibold text-ink tracking-[-0.224px]">Windows</p>
                <ul className="mt-1 text-[14px] text-ink-subtle leading-[1.43] tracking-[-0.224px] space-y-0.5">
                  <li>Windows 10/11 (64-bit)</li>
                  <li>WebView2 Runtime (included in Win 11)</li>
                </ul>
              </div>
              <div>
                <p className="text-[14px] font-semibold text-ink tracking-[-0.224px]">macOS</p>
                <ul className="mt-1 text-[14px] text-ink-subtle leading-[1.43] tracking-[-0.224px] space-y-0.5">
                  <li>macOS 10.15 (Catalina) or later</li>
                  <li>Apple Silicon or Intel</li>
                </ul>
              </div>
            </div>
          </Step>

          {/* Step 1 */}
          <Step title="1. Download & Install">
            <p className="text-[17px] text-ink-subtle leading-[1.47] tracking-[-0.374px]">
              Download the latest installer from GitHub Releases, or use winget on Windows:
            </p>
            <div className="mt-4 space-y-3">
              <CodeBlock title="Windows — winget">{`winget install jithin-jz.telegrab`}</CodeBlock>
              <CodeBlock title="Windows — manual">{`# Download the Setup installer from:
https://github.com/jithin-jz/telegrab/releases/latest

# Run the installer
Telegrab-1.4.0-Setup.exe`}</CodeBlock>
              <CodeBlock title="macOS">{`# Download the .dmg or .zip from:
https://github.com/jithin-jz/telegrab/releases/latest

# Drag Telegrab.app to Applications`}</CodeBlock>
            </div>
          </Step>

          {/* Step 2 */}
          <Step title="2. Get Telegram API Keys">
            <p className="text-[17px] text-ink-subtle leading-[1.47] tracking-[-0.374px]">
              You need your own Telegram API credentials. This is a one-time setup:
            </p>
            <ol className="mt-4 list-decimal list-inside space-y-2 text-[17px] text-ink-subtle leading-[1.47] tracking-[-0.374px]">
              <li>Visit <a href="https://my.telegram.org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">my.telegram.org</a></li>
              <li>Log in with your phone number</li>
              <li>Go to <strong className="text-ink font-semibold">API development tools</strong></li>
              <li>Create a new application</li>
              <li>Copy your <strong className="text-ink font-semibold">API ID</strong> and <strong className="text-ink font-semibold">API Hash</strong></li>
            </ol>
          </Step>

          {/* Step 3 */}
          <Step title="3. Sign In">
            <p className="text-[17px] text-ink-subtle leading-[1.47] tracking-[-0.374px]">
              Launch Telegrab and enter your API credentials. Then sign in using:
            </p>
            <ul className="mt-4 list-disc list-inside space-y-2 text-[17px] text-ink-subtle leading-[1.47] tracking-[-0.374px]">
              <li><strong className="text-ink font-semibold">QR Code</strong> — Scan with your Telegram mobile app</li>
              <li><strong className="text-ink font-semibold">Phone Number</strong> — Enter your number and the verification code</li>
            </ul>
          </Step>

          {/* Step 4 */}
          <Step title="4. Start Using">
            <p className="text-[17px] text-ink-subtle leading-[1.47] tracking-[-0.374px]">
              You're all set. Telegrab shows your Saved Messages as the default storage.
              Create folders, upload files via drag & drop, and stream media directly.
            </p>
            <div className="mt-4 rounded-[18px] border border-hairline bg-parchment p-6">
              <p className="text-[14px] font-semibold text-ink tracking-[-0.224px]">Tips</p>
              <ul className="mt-2 space-y-1 text-[14px] text-ink-subtle leading-[1.43] tracking-[-0.224px]">
                <li>Use <kbd className="rounded-[5px] border border-hairline bg-canvas px-1.5 py-0.5 text-[12px] font-mono">Ctrl+K</kbd> to open the command palette</li>
                <li>Drag files directly into the window to upload</li>
                <li>Right-click files for context menu options</li>
                <li>Enable the REST API in Settings for automation</li>
              </ul>
            </div>
          </Step>

          {/* Uninstall */}
          <Step title="Uninstall">
            <div className="space-y-3">
              <CodeBlock title="Windows">{`# Via Settings
Settings → Apps → Installed apps → Telegrab → Uninstall

# Via winget
winget uninstall jithin-jz.telegrab`}</CodeBlock>
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
    >
      <h2 className="font-display text-[28px] font-semibold leading-[1.14] tracking-[0.196px] text-ink">{title}</h2>
      <div className="mt-4">{children}</div>
    </motion.div>
  )
}
