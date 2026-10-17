import { useEffect, useState, type ReactNode } from 'react'
import { Check, Copy, Info, TriangleAlert } from 'lucide-react'
import { AppleIcon, LinuxIcon, WindowsIcon } from '../components/ui'
import { REPO_URL, RELEASES_URL, useDownloadUrl, type Platform } from '../hooks/useDownloadUrl'

const SECTIONS = [
  { id: 'requirements', title: 'Requirements' },
  { id: 'install', title: 'Install' },
  { id: 'api-keys', title: 'Get API keys' },
  { id: 'sign-in', title: 'Sign in' },
  { id: 'using', title: 'Using Telegrab' },
  { id: 'data', title: 'Where data lives' },
  { id: 'troubleshooting', title: 'Troubleshooting' },
  { id: 'uninstall', title: 'Uninstall' },
]

const PLATFORMS: { id: Platform; label: string; icon: (p: { className?: string }) => ReactNode }[] = [
  { id: 'windows', label: 'Windows', icon: WindowsIcon },
  { id: 'mac', label: 'macOS', icon: AppleIcon },
  { id: 'linux', label: 'Linux', icon: LinuxIcon },
]

export function Docs() {
  const { os } = useDownloadUrl()
  const [platform, setPlatform] = useState<Platform>(os === 'unknown' ? 'windows' : os)
  const active = useActiveSection(SECTIONS.map((s) => s.id))

  return (
    <div className="mx-auto max-w-[1200px] px-5 sm:px-6">
      <header className="border-b border-hairline py-14 sm:py-20">
        <h1 className="text-gradient text-[36px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[52px]">
          Installation guide
        </h1>
        <p className="mt-4 max-w-[560px] text-[17px] leading-[1.65] text-slate">
          Get Telegrab running in about five minutes, from download to your first upload.
        </p>
      </header>

      <div className="grid gap-12 py-12 lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-16 lg:py-16">
        <aside className="hidden lg:block">
          <nav className="sticky top-24" aria-label="On this page">
            <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.12em] text-steel">On this page</p>
            <ul className="space-y-0.5 border-l border-hairline">
              {SECTIONS.map((s) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    className={`-ml-px block border-l py-1.5 pl-4 text-[14px] transition-colors ${
                      active === s.id
                        ? 'border-primary font-medium text-ink'
                        : 'border-transparent text-steel hover:text-ink'
                    }`}
                  >
                    {s.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <article className="min-w-0 max-w-[760px] space-y-16">
          <Section id="requirements" title="Requirements">
            <div className="grid gap-3 sm:grid-cols-3">
              <Req icon={WindowsIcon} name="Windows" items={['Windows 10 or 11, 64-bit', 'WebView2 Runtime (built into Windows 11)']} />
              <Req icon={AppleIcon} name="macOS" items={['macOS 11 Big Sur or later', 'Apple Silicon (M1 or later)']} />
              <Req icon={LinuxIcon} name="Linux" items={['x86-64 distribution', 'GTK 3 and WebKitGTK 4.1']} />
            </div>
            <P>You also need a Telegram account and an internet connection.</P>
          </Section>

          <Section id="install" title="Install">
            <P>
              Download the latest build from{' '}
              <A href={RELEASES_URL}>GitHub Releases</A>, then follow the steps for your system.
            </P>
            <div role="tablist" aria-label="Operating system" className="mt-6 inline-flex rounded-full border border-hairline bg-surface p-1">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="tab"
                  aria-selected={platform === p.id}
                  onClick={() => setPlatform(p.id)}
                  className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-[14px] font-medium transition-colors ${
                    platform === p.id ? 'bg-surface-3 text-ink' : 'text-steel hover:text-ink'
                  }`}
                >
                  <p.icon className="h-3.5 w-3.5" />
                  {p.label}
                </button>
              ))}
            </div>

            <div role="tabpanel" className="mt-6 space-y-4">
              {platform === 'windows' && (
                <>
                  <Steps
                    items={[
                      <>Download <Code>telegrab-windows-setup.exe</Code>.</>,
                      <>Run it and follow the installer. Telegrab appears in the Start menu.</>,
                      <>Prefer not to install? Use <Code>telegrab-windows-portable.exe</Code> instead and run it from any folder.</>,
                    ]}
                  />
                  <Callout tone="warn">
                    If SmartScreen shows <em>Windows protected your PC</em>, click <strong>More info</strong>, then{' '}
                    <strong>Run anyway</strong>. Builds are not yet code-signed.
                  </Callout>
                </>
              )}
              {platform === 'mac' && (
                <>
                  <Steps
                    items={[
                      <>Download <Code>telegrab-macos.zip</Code> and open it to extract the app.</>,
                      <>Drag <Code>telegrab.app</Code> into your Applications folder.</>,
                      <>Open it from Applications or Launchpad.</>,
                    ]}
                  />
                  <Callout tone="warn">
                    If macOS says the app cannot be opened, go to <strong>System Settings, Privacy &amp; Security</strong>{' '}
                    and click <strong>Open Anyway</strong>. Builds are not yet code-signed.
                  </Callout>
                </>
              )}
              {platform === 'linux' && (
                <>
                  <P>Install the WebKitGTK runtime if you do not have it (Debian and Ubuntu shown):</P>
                  <CodeBlock>{`sudo apt install libwebkit2gtk-4.1-0`}</CodeBlock>
                  <P>Then extract the archive and start the app:</P>
                  <CodeBlock>{`tar -xzf telegrab-linux.tar.gz
./telegrab/telegrab`}</CodeBlock>
                </>
              )}
              <Callout>
                Each release includes a <A href={`${REPO_URL}/releases/latest`}>SHA256SUMS</A> file. Compare it with
                your download&apos;s hash to confirm it has not been tampered with.
              </Callout>
            </div>
          </Section>

          <Section id="api-keys" title="Get your API keys">
            <P>
              Telegram requires every client app to identify itself with an API ID and hash. They are free and you
              only need to create them once.
            </P>
            <Steps
              items={[
                <>Go to <A href="https://my.telegram.org">my.telegram.org</A> and log in with your phone number.</>,
                <>Open <strong className="text-ink">API development tools</strong>.</>,
                <>Fill in the form to create an application. Any app title and short name will do.</>,
                <>Copy the <strong className="text-ink">App api_id</strong> and <strong className="text-ink">App api_hash</strong>.</>,
              ]}
            />
            <Callout tone="warn">Treat the API hash like a password. Never share it or post it publicly.</Callout>
          </Section>

          <Section id="sign-in" title="Sign in">
            <P>Start Telegrab, paste your API ID and hash, then choose how to sign in:</P>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Card title="QR code">
                On your phone, open Telegram, go to Settings, Devices, Link Desktop Device, and scan the code.
              </Card>
              <Card title="Phone number">
                Enter your number and the code Telegram sends you, plus your two-step verification password if you
                have one.
              </Card>
            </div>
          </Section>

          <Section id="using" title="Using Telegrab">
            <P>
              Saved Messages is your default storage. Create folders to organise files; each folder is a private
              channel in your account that only you can see.
            </P>
            <ul className="mt-5 divide-y divide-hairline rounded-2xl border border-hairline bg-surface">
              <Tip keys={['Ctrl', 'K']}>Open the command palette to jump to files and actions</Tip>
              <Tip label="Drag and drop">Drop files onto the window to upload them</Tip>
              <Tip label="Right-click">Preview, download, rename, pin to Quick Access or delete a file</Tip>
              <Tip label="Vaults">Encrypt sensitive files on your device with AES-256-GCM before upload</Tip>
              <Tip label="Settings">Configure a SOCKS5, SOCKS4, HTTP or MTProxy proxy</Tip>
            </ul>
            <P className="mt-5">
              Files up to 2 GB are supported, or 4 GB with Telegram Premium. Video, audio and PDFs stream without a
              full download.
            </P>
          </Section>

          <Section id="data" title="Where data lives">
            <P>
              Your files live in Telegram. On your computer Telegrab keeps only its session, settings and logs in the
              app data folder, and thumbnails in a cache folder that is safe to delete.
            </P>
            <div className="mt-5 overflow-hidden rounded-2xl border border-hairline">
              <table className="w-full text-left text-[14px]">
                <thead className="bg-surface-2 text-[12px] uppercase tracking-[0.08em] text-steel">
                  <tr>
                    <th className="px-4 py-3 font-semibold">System</th>
                    <th className="px-4 py-3 font-semibold">App data</th>
                    <th className="hidden px-4 py-3 font-semibold sm:table-cell">Cache</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline bg-surface font-mono text-[13px] text-slate">
                  <tr>
                    <td className="px-4 py-3 font-sans text-ink">Windows</td>
                    <td className="break-all px-4 py-3">%APPDATA%\telegrab</td>
                    <td className="hidden break-all px-4 py-3 sm:table-cell">%LOCALAPPDATA%\telegrab</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 font-sans text-ink">macOS</td>
                    <td className="break-all px-4 py-3">~/Library/Application Support/telegrab</td>
                    <td className="hidden break-all px-4 py-3 sm:table-cell">~/Library/Caches/telegrab</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 font-sans text-ink">Linux</td>
                    <td className="break-all px-4 py-3">~/.local/share/telegrab</td>
                    <td className="hidden break-all px-4 py-3 sm:table-cell">~/.cache/telegrab</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Section>

          <Section id="troubleshooting" title="Troubleshooting">
            <div className="space-y-3">
              <Card title="The app does not start on Linux">
                Make sure WebKitGTK 4.1 is installed (<Code>libwebkit2gtk-4.1-0</Code> on Debian and Ubuntu), then run{' '}
                <Code>./telegrab/telegrab</Code> from a terminal to see any error.
              </Card>
              <Card title="Transfers pause or stall">
                Telegrab pauses automatically when the network drops or Telegram rate-limits the account, and resumes
                on its own. On restricted networks, set a proxy in Settings.
              </Card>
              <Card title="Something else went wrong">
                Check <Code>telegrab.log</Code> in the app data folder above, then{' '}
                <A href={`${REPO_URL}/issues`}>open an issue</A> with the relevant lines. Remove phone numbers and API
                keys before posting.
              </Card>
            </div>
          </Section>

          <Section id="uninstall" title="Uninstall">
            <div className="space-y-3">
              <Card title="Windows">Settings, Apps, Installed apps, Telegrab, Uninstall. For the portable build, delete the .exe.</Card>
              <Card title="macOS">Move telegrab.app from Applications to the Trash.</Card>
              <Card title="Linux">Delete the extracted telegrab folder.</Card>
            </div>
            <P className="mt-5">
              To also sign out and remove local data, delete the app data and cache folders listed above. Files you
              uploaded stay in your Telegram account.
            </P>
          </Section>
        </article>
      </div>
    </div>
  )
}

/** Id of the section currently nearest the top of the viewport. */
function useActiveSection(ids: string[]) {
  const [active, setActive] = useState(ids[0])
  const key = ids.join(',')

  useEffect(() => {
    const els = key.split(',').map((id) => document.getElementById(id)).filter((el): el is HTMLElement => !!el)
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
        if (hit) setActive(hit.target.id)
      },
      { rootMargin: '-80px 0px -65% 0px' },
    )
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [key])

  return active
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id}>
      <h2 className="group flex items-center gap-2 text-[24px] font-semibold tracking-[-0.02em] text-ink sm:text-[28px]">
        <a href={`#${id}`} className="hover:text-primary-ink">{title}</a>
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function P({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`text-[16px] leading-[1.7] text-slate ${className}`}>{children}</p>
}

function A({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="font-medium text-ink underline decoration-primary/60 underline-offset-4 hover:decoration-primary">
      {children}
    </a>
  )
}

function Code({ children }: { children: ReactNode }) {
  return <code className="rounded-md border border-hairline bg-surface-2 px-1.5 py-0.5 font-mono text-[13px] text-ink">{children}</code>
}

function CodeBlock({ children }: { children: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(children).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }, () => {})
  }
  return (
    <div className="group relative rounded-xl border border-hairline bg-surface">
      <pre className="overflow-x-auto p-4 pr-14 font-mono text-[13.5px] leading-[1.7] text-ink">
        <code>{children}</code>
      </pre>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? 'Copied' : 'Copy to clipboard'}
        className="absolute right-2.5 top-2.5 flex h-8 w-8 items-center justify-center rounded-lg border border-hairline bg-surface-2 text-steel transition hover:text-ink"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  )
}

function Steps({ items }: { items: ReactNode[] }) {
  return (
    <ol className="mt-5 space-y-3">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3.5 text-[16px] leading-[1.7] text-slate">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary-ink">
            {i + 1}
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ol>
  )
}

function Callout({ tone = 'info', children }: { tone?: 'info' | 'warn'; children: ReactNode }) {
  const warn = tone === 'warn'
  const Icon = warn ? TriangleAlert : Info
  return (
    <div
      className={`mt-5 flex gap-3 rounded-xl border px-4 py-3.5 text-[14.5px] leading-[1.6] ${
        warn ? 'border-warning/25 bg-warning/[0.06] text-[#e9dca6]' : 'border-primary/25 bg-primary-soft text-[#cfe0fd]'
      }`}
    >
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${warn ? 'text-warning' : 'text-primary-ink'}`} aria-hidden="true" />
      <div className="[&_strong]:text-ink">{children}</div>
    </div>
  )
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-5">
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      <p className="mt-1.5 text-[14.5px] leading-[1.65] text-slate">{children}</p>
    </div>
  )
}

function Req({ icon: Icon, name, items }: { icon: (p: { className?: string }) => ReactNode; name: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-5">
      <div className="flex items-center gap-2 text-[15px] font-semibold text-ink">
        <Icon className="h-4 w-4" />
        {name}
      </div>
      <ul className="mt-3 space-y-1.5 text-[14px] leading-[1.55] text-slate">
        {items.map((it) => (
          <li key={it}>{it}</li>
        ))}
      </ul>
    </div>
  )
}

function Tip({ keys, label, children }: { keys?: string[]; label?: string; children: ReactNode }) {
  return (
    <li className="flex flex-col gap-1.5 px-5 py-4 sm:flex-row sm:items-center sm:gap-6">
      <span className="flex shrink-0 gap-1 sm:w-[140px]">
        {keys ? (
          keys.map((k) => (
            <kbd key={k} className="rounded-md border border-hairline-strong bg-surface-2 px-2 py-0.5 font-mono text-[12px] text-ink">
              {k}
            </kbd>
          ))
        ) : (
          <span className="text-[14px] font-semibold text-ink">{label}</span>
        )}
      </span>
      <span className="text-[14.5px] text-slate">{children}</span>
    </li>
  )
}
