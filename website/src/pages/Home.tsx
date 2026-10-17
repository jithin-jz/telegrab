import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ChevronDown,
  CirclePlay,
  CloudOff,
  Download,
  FolderTree,
  Gauge,
  Globe,
  HardDrive,
  KeyRound,
  Laptop,
  LockKeyhole,
  QrCode,
  RefreshCw,
  ShieldCheck,
  WifiOff,
} from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'
import { AppMockup } from '../components/AppMockup'
import {
  AppleIcon,
  GitHubIcon,
  LinuxIcon,
  Reveal,
  SectionHeading,
  WindowsIcon,
  btnPrimary,
  btnSecondary,
} from '../components/ui'
import { PLATFORM_NAME, REPO_URL, useDownloadUrl, type Build } from '../hooks/useDownloadUrl'

type Icon = ComponentType<{ className?: string }>

export function Home() {
  return (
    <>
      <Hero />
      <Highlights />
      <Features />
      <HowItWorks />
      <Privacy />
      <Downloads />
      <Faq />
      <FinalCta />
    </>
  )
}

/* ------------------------------------------------------------------ Hero */

function Hero() {
  const { url, label, os } = useDownloadUrl()
  const others = (['windows', 'mac', 'linux'] as const).filter((p) => p !== os)

  return (
    <section className="relative -mt-16 overflow-hidden pt-16">
      <div className="hero-glow pointer-events-none absolute inset-0" />
      <div className="grid-bg pointer-events-none absolute inset-0" />

      <div className="relative mx-auto max-w-[1200px] px-5 pb-20 pt-16 sm:px-6 sm:pt-24">
        <div className="mx-auto max-w-[1000px] text-center">
          <h1 className="text-gradient text-balance text-[42px] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-[64px] lg:text-[72px]">
            Your Telegram,
            <br />
            as unlimited cloud storage.
          </h1>
          <p className="mx-auto mt-6 max-w-[560px] text-[17px] leading-[1.65] text-slate sm:text-[19px]">
            Telegrab is a free, open-source desktop app that stores, streams and organises your files
            inside your own Telegram account. No quota, no subscription, no middleman.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href={url} className={`${btnPrimary} w-full px-6 py-3 text-[15px] sm:w-auto`}>
              <Download className="h-4 w-4" aria-hidden="true" />
              {label}
            </a>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={`${btnSecondary} w-full px-6 py-3 text-[15px] sm:w-auto`}
            >
              <GitHubIcon />
              View on GitHub
            </a>
          </div>
          <p className="mt-4 text-[13px] text-steel">
            {os === 'unknown' ? 'Windows, macOS and Linux' : (
              <>
                Also for{' '}
                {others.map((p, i) => (
                  <span key={p}>
                    {i > 0 && ' and '}
                    <a href="#download" className="text-slate underline-offset-4 hover:text-ink hover:underline">
                      {PLATFORM_NAME[p]}
                    </a>
                  </span>
                ))}
              </>
            )}
            <span className="mx-2 text-hairline-strong">·</span>
            MIT licensed
          </p>
        </div>

        <Reveal delay={150} className="mx-auto mt-16 max-w-[1000px] sm:mt-20">
          <AppMockup />
        </Reveal>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ Highlights */

function Highlights() {
  const items = [
    { value: 'No quota', label: 'on total storage' },
    { value: 'AES-256', label: 'encrypted vaults' },
    { value: '3 platforms', label: 'Windows, macOS, Linux' },
    { value: '100%', label: 'open source, MIT' },
  ]
  return (
    <section className="border-y border-hairline bg-surface/50">
      <div className="mx-auto grid max-w-[1200px] grid-cols-2 px-5 sm:px-6 md:grid-cols-4">
        {items.map((it, i) => (
          <div
            key={it.value}
            className={`px-4 py-8 text-center ${i % 2 === 1 ? 'border-l border-hairline' : ''} ${
              i >= 2 ? 'border-t border-hairline md:border-t-0' : ''
            } ${i === 2 ? 'md:border-l' : ''}`}
          >
            <p className="text-[24px] font-semibold tracking-[-0.02em] text-ink sm:text-[28px]">{it.value}</p>
            <p className="mt-1 text-[13px] text-steel">{it.label}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

/* -------------------------------------------------------------- Features */

const FEATURES: { icon: Icon; title: string; desc: string; wide?: boolean }[] = [
  {
    icon: HardDrive,
    title: 'Storage without a ceiling',
    desc: 'Files live in your own Telegram account, so there is no total storage quota and nothing to pay. Single files can be up to 2 GB, or 4 GB with Telegram Premium.',
    wide: true,
  },
  {
    icon: Gauge,
    title: 'Fast transfers',
    desc: 'Parallel, pipelined uploads and downloads over a pooled connection, with automatic per-part retries.',
  },
  {
    icon: CirclePlay,
    title: 'Stream instantly',
    desc: 'Play video and audio and view PDFs straight from the cloud, with seeking, without downloading the whole file.',
  },
  {
    icon: LockKeyhole,
    title: 'Encrypted vaults',
    desc: 'AES-256-GCM encryption happens on your device before upload. Vaults keep working across reinstalls and devices.',
  },
  {
    icon: FolderTree,
    title: 'Folders and search',
    desc: 'Organise files into folders, drag and drop to upload, and find anything with search and the Ctrl K command palette.',
    wide: true,
  },
  {
    icon: WifiOff,
    title: 'Resilient queue',
    desc: 'Transfers pause when the network drops and pick up again when it comes back.',
  },
  {
    icon: Globe,
    title: 'Proxy support',
    desc: 'Connect through SOCKS5, SOCKS4, HTTP or MTProxy on restricted networks.',
    wide: true,
  },
  {
    icon: RefreshCw,
    title: 'Verified updates',
    desc: 'Automatic, checksum-verified updates on Windows. macOS and Linux link straight to the new release.',
    wide: true,
  },
]

function Features() {
  return (
    <section id="features" className="mx-auto max-w-[1200px] px-5 py-24 sm:px-6 sm:py-32">
      <SectionHeading title="Everything a cloud drive should be">
        A real file manager on top of Telegram, built for large libraries and large files.
      </SectionHeading>

      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map((f, i) => (
          <Reveal
            key={f.title}
            delay={(i % 4) * 60}
            className={`group rounded-2xl border border-hairline bg-surface p-6 transition-colors hover:border-hairline-strong hover:bg-surface-2 ${
              f.wide ? 'lg:col-span-2' : ''
            }`}
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary-ink">
              <f.icon className="h-5 w-5" aria-hidden="true" />
            </div>
            <h3 className="mt-5 text-[17px] font-semibold tracking-[-0.01em] text-ink">{f.title}</h3>
            <p className="mt-2 text-[15px] leading-[1.6] text-slate">{f.desc}</p>
          </Reveal>
        ))}
      </div>
    </section>
  )
}

/* ---------------------------------------------------------- How it works */

const STEPS: { icon: Icon; title: string; desc: ReactNode }[] = [
  {
    icon: Laptop,
    title: 'Install Telegrab',
    desc: 'Download the build for your system and install it like any other desktop app.',
  },
  {
    icon: KeyRound,
    title: 'Add your API keys',
    desc: (
      <>
        Create a free API ID and hash at{' '}
        <a href="https://my.telegram.org" target="_blank" rel="noopener noreferrer" className="text-ink underline underline-offset-4">
          my.telegram.org
        </a>
        . It takes about a minute.
      </>
    ),
  },
  {
    icon: QrCode,
    title: 'Sign in and upload',
    desc: 'Scan a QR code or use your phone number, then drag files in. Everything lands in your Telegram account.',
  },
]

function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t border-hairline bg-surface/40">
      <div className="mx-auto max-w-[1200px] px-5 py-24 sm:px-6 sm:py-32">
        <SectionHeading title="Up and running in three steps" />

        <div className="relative mt-16">
          <div className="pointer-events-none absolute left-[16.6%] right-[16.6%] top-7 hidden h-px bg-gradient-to-r from-transparent via-hairline-strong to-transparent md:block" />
        <ol className="grid gap-10 md:grid-cols-3 md:gap-6">
          {STEPS.map((s, i) => (
            <Reveal as="li" key={s.title} delay={i * 100} className="relative text-center">
              <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-hairline-strong bg-surface-2 text-primary-ink">
                <s.icon className="h-6 w-6" aria-hidden="true" />
                <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-[12px] font-semibold text-canvas">
                  {i + 1}
                </span>
              </div>
              <h3 className="mt-6 text-[18px] font-semibold text-ink">{s.title}</h3>
              <p className="mx-auto mt-2 max-w-[300px] text-[15px] leading-[1.6] text-slate">{s.desc}</p>
            </Reveal>
          ))}
        </ol>
        </div>

        <Reveal className="mt-14 text-center">
          <Link to="/docs" className={btnSecondary}>
            Read the installation guide
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Reveal>
      </div>
    </section>
  )
}

/* --------------------------------------------------------------- Privacy */

function Privacy() {
  const points: { icon: Icon; title: string; desc: string }[] = [
    {
      icon: CloudOff,
      title: 'No Telegrab servers',
      desc: 'The app talks directly to Telegram. There is no account to create with us and nothing in between.',
    },
    {
      icon: ShieldCheck,
      title: 'Credentials stay local',
      desc: 'Your session and API keys are stored only on your computer, in your user app data folder.',
    },
    {
      icon: LockKeyhole,
      title: 'Encrypt what matters',
      desc: 'Put sensitive files in a vault and they are encrypted before they leave your device.',
    },
  ]

  return (
    <section className="mx-auto max-w-[1200px] px-5 py-24 sm:px-6 sm:py-32">
      <div className="grid items-center gap-14 lg:grid-cols-2">
        <div>
          <Reveal>
            <h2 className="text-gradient text-balance text-[32px] font-semibold leading-[1.15] tracking-[-0.02em] sm:text-[44px]">
              Between you and Telegram. Nobody else.
            </h2>
            <p className="mt-4 max-w-[520px] text-[17px] leading-[1.65] text-slate">
              Telegrab is a client, not a service. Your files are stored in private channels in your own
              account, and the source code is open for anyone to audit.
            </p>
          </Reveal>
          <div className="mt-10 space-y-6">
            {points.map((p, i) => (
              <Reveal key={p.title} delay={i * 80} className="flex gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 text-primary-ink">
                  <p.icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <h3 className="text-[16px] font-semibold text-ink">{p.title}</h3>
                  <p className="mt-1 text-[15px] leading-[1.6] text-slate">{p.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>

        <Reveal delay={100}>
          <DataFlow />
        </Reveal>
      </div>
    </section>
  )
}

function DataFlow() {
  const node = 'rounded-2xl border border-hairline-strong bg-surface-2 px-5 py-4 text-center'
  return (
    <div className="rounded-3xl border border-hairline bg-surface p-6 sm:p-10" aria-label="Your device connects directly to Telegram">
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        <div className={`${node} sm:flex-1`}>
          <Laptop className="mx-auto h-6 w-6 text-ink" aria-hidden="true" />
          <p className="mt-2 text-[14px] font-semibold text-ink">Your device</p>
          <p className="text-[12px] text-steel">Telegrab app</p>
        </div>
        <div className="flex flex-col items-center px-2 py-1 text-[11px] font-medium text-primary-ink sm:py-0">
          <span className="hidden h-px w-16 bg-gradient-to-r from-primary/20 via-primary to-primary/20 sm:block" />
          <span className="h-8 w-px bg-gradient-to-b from-primary/20 via-primary to-primary/20 sm:hidden" />
          <span className="mt-2">MTProto</span>
        </div>
        <div className={`${node} sm:flex-1`}>
          <svg className="mx-auto h-6 w-6 text-[#5b8def]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M21.9 4.6 18.7 19.7c-.2 1-.9 1.3-1.7.8l-4.8-3.5-2.3 2.2c-.3.3-.5.5-1 .5l.3-4.9 8.9-8c.4-.3-.1-.5-.6-.2L6.6 13.5 1.9 12c-1-.3-1-1 .2-1.5L20.6 3.4c.9-.3 1.6.2 1.3 1.2z" />
          </svg>
          <p className="mt-2 text-[14px] font-semibold text-ink">Telegram</p>
          <p className="text-[12px] text-steel">Your account</p>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-center gap-2 rounded-xl border border-dashed border-hairline-strong px-4 py-3 text-[13px] text-steel">
        <CloudOff className="h-4 w-4" aria-hidden="true" />
        No Telegrab servers in the path
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- Downloads */

function Downloads() {
  const { os, version, build } = useDownloadUrl()

  const cards: {
    id: 'windows' | 'mac' | 'linux'
    icon: Icon
    note: string
    builds: { build: Build; label: string }[]
  }[] = [
    {
      id: 'windows',
      icon: WindowsIcon,
      note: 'Windows 10 or 11, 64-bit',
      builds: [
        { build: 'windows', label: 'Installer (.exe)' },
        { build: 'windows-portable', label: 'Portable (.exe)' },
      ],
    },
    {
      id: 'mac',
      icon: AppleIcon,
      note: 'macOS 11 or later, Apple Silicon',
      builds: [{ build: 'mac', label: 'App bundle (.zip)' }],
    },
    {
      id: 'linux',
      icon: LinuxIcon,
      note: 'x86-64 with WebKitGTK 4.1',
      builds: [{ build: 'linux', label: 'Archive (.tar.gz)' }],
    },
  ]

  return (
    <section id="download" className="border-t border-hairline bg-surface/40">
      <div className="mx-auto max-w-[1200px] px-5 py-24 sm:px-6 sm:py-32">
        <SectionHeading title="Get Telegrab">
          {version ? `Version ${version.replace(/^v/, '')}. ` : ''}Free for every platform.
        </SectionHeading>

        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {cards.map((c, i) => {
            const recommended = c.id === os
            return (
              <Reveal
                key={c.id}
                delay={i * 80}
                className={`relative flex flex-col rounded-2xl border p-6 ${
                  recommended
                    ? 'border-primary/50 bg-gradient-to-b from-primary-soft to-surface'
                    : 'border-hairline bg-surface'
                }`}
              >
                {recommended && (
                  <span className="absolute right-5 top-5 rounded-full bg-primary px-2.5 py-0.5 text-[11px] font-semibold text-canvas">
                    Your system
                  </span>
                )}
                <c.icon className="h-7 w-7 text-ink" />
                <h3 className="mt-5 text-[20px] font-semibold text-ink">{PLATFORM_NAME[c.id]}</h3>
                <p className="mt-1 text-[14px] text-steel">{c.note}</p>
                <div className="mt-6 flex flex-1 flex-col justify-end gap-2">
                  {c.builds.map((b, j) => {
                    const { url, size } = build(b.build)
                    return (
                      <a
                        key={b.build}
                        href={url}
                        className={`flex items-center justify-between rounded-xl px-4 py-3 text-[14px] font-semibold transition active:scale-[0.99] ${
                          j === 0
                            ? recommended
                              ? 'bg-primary text-canvas hover:bg-primary-hover'
                              : 'bg-ink text-canvas hover:bg-white'
                            : 'border border-hairline-strong text-ink hover:bg-white/[0.05]'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <Download className="h-4 w-4" aria-hidden="true" />
                          {b.label}
                        </span>
                        {size && <span className="text-[12px] font-medium opacity-70">{size}</span>}
                      </a>
                    )
                  })}
                </div>
              </Reveal>
            )
          })}
        </div>

        <p className="mx-auto mt-8 max-w-[680px] text-center text-[13px] leading-[1.6] text-steel">
          Builds are not yet code-signed, so SmartScreen or Gatekeeper may warn on first launch. Every release
          includes a{' '}
          <a href={build('checksums').url} className="text-slate underline underline-offset-4 hover:text-ink">
            SHA256SUMS
          </a>{' '}
          file to verify your download.{' '}
          <a href={`${REPO_URL}/releases`} target="_blank" rel="noopener noreferrer" className="text-slate underline underline-offset-4 hover:text-ink">
            All releases
          </a>
        </p>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------- FAQ */

const FAQ: { q: string; a: ReactNode }[] = [
  {
    q: 'Is the storage really unlimited?',
    a: 'Telegram does not cap the total amount you can store in your account, and Telegrab adds no limits of its own. Each individual file can be up to 2 GB, or 4 GB if you have Telegram Premium.',
  },
  {
    q: 'Where are my files actually stored?',
    a: 'In your own Telegram account. Saved Messages is the default location, and each folder you create is a private channel that only you can see.',
  },
  {
    q: 'Can the Telegrab developers see my files?',
    a: 'No. There are no Telegrab servers. The app connects directly to Telegram, and your session and API keys never leave your computer. For extra protection, use an encrypted vault.',
  },
  {
    q: 'Why do I need my own API ID and hash?',
    a: (
      <>
        Telegram requires every client app to identify itself. Using your own keys from{' '}
        <a href="https://my.telegram.org" target="_blank" rel="noopener noreferrer" className="text-ink underline underline-offset-4">
          my.telegram.org
        </a>{' '}
        keeps your access independent of anyone else. They are free and take about a minute to create.
      </>
    ),
  },
  {
    q: 'Why does my system warn me when I open it?',
    a: 'Release builds are not yet code-signed, so Windows SmartScreen and macOS Gatekeeper show a warning the first time. You can verify any download against the SHA256SUMS file published with each release.',
  },
  {
    q: 'Is Telegrab affiliated with Telegram?',
    a: 'No. Telegrab is an independent, unofficial, open-source client released under the MIT license. It is not affiliated with or endorsed by Telegram.',
  },
]

function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-[820px] px-5 py-24 sm:px-6 sm:py-32">
      <SectionHeading title="Questions, answered" />
      <div className="mt-12 divide-y divide-hairline rounded-2xl border border-hairline bg-surface">
        {FAQ.map((item) => (
          <details key={item.q} className="group px-6">
            <summary className="flex cursor-pointer items-center justify-between gap-4 py-5 text-[16px] font-medium text-ink">
              {item.q}
              <ChevronDown className="faq-chevron h-4 w-4 shrink-0 text-steel transition-transform duration-200" aria-hidden="true" />
            </summary>
            <p className="pb-6 pr-8 text-[15px] leading-[1.65] text-slate">{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------- Final CTA */

function FinalCta() {
  const { url, label } = useDownloadUrl()
  return (
    <section className="px-5 pb-24 sm:px-6 sm:pb-32">
      <Reveal className="relative mx-auto max-w-[1200px] overflow-hidden rounded-3xl border border-hairline-strong bg-surface px-6 py-16 text-center sm:py-20">
        <div className="hero-glow pointer-events-none absolute inset-0 opacity-80" />
        <div className="relative">
          <h2 className="text-gradient mx-auto max-w-[620px] text-balance text-[32px] font-semibold leading-[1.15] tracking-[-0.02em] sm:text-[44px]">
            Stop paying for cloud storage.
          </h2>
          <p className="mx-auto mt-4 max-w-[480px] text-[17px] leading-[1.65] text-slate">
            Install Telegrab and turn the Telegram account you already have into your drive.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href={url} className={`${btnPrimary} px-6 py-3 text-[15px]`}>
              <Download className="h-4 w-4" aria-hidden="true" />
              {label}
            </a>
            <Link to="/docs" className={`${btnSecondary} px-6 py-3 text-[15px]`}>
              Installation guide
            </Link>
          </div>
        </div>
      </Reveal>
    </section>
  )
}
