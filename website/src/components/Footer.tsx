import { Link } from 'react-router-dom'
import { REPO_URL, useDownloadUrl } from '../hooks/useDownloadUrl'
import { GitHubIcon, Logo } from './ui'

const COLUMNS: { title: string; links: { label: string; href: string; internal?: boolean }[] }[] = [
  {
    title: 'Product',
    links: [
      { label: 'Features', href: '/#features', internal: true },
      { label: 'Download', href: '/#download', internal: true },
      { label: 'FAQ', href: '/#faq', internal: true },
      { label: 'Changelog', href: `${REPO_URL}/releases` },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Documentation', href: '/docs', internal: true },
      { label: 'Source code', href: REPO_URL },
      { label: 'Report an issue', href: `${REPO_URL}/issues` },
      { label: 'MIT License', href: `${REPO_URL}/blob/main/LICENSE` },
    ],
  },
  {
    title: 'Developer',
    links: [
      { label: 'GitHub', href: 'https://github.com/jithin-jz' },
      { label: 'LinkedIn', href: 'https://www.linkedin.com/in/jithin-kr' },
    ],
  },
]

const linkClass = 'text-[14px] text-slate transition-colors hover:text-ink'

export function Footer() {
  const { version } = useDownloadUrl()
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto max-w-[1200px] px-5 py-14 sm:px-6">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div className="max-w-[300px]">
            <Link to="/" className="flex items-center gap-2.5">
              <Logo />
              <span className="text-[16px] font-semibold text-ink">Telegrab</span>
            </Link>
            <p className="mt-4 text-[14px] leading-[1.6] text-steel">
              Free, open-source cloud storage built on your own Telegram account.
            </p>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-5 inline-flex items-center gap-2 rounded-full border border-hairline-strong px-3.5 py-1.5 text-[13px] font-medium text-slate transition hover:text-ink"
            >
              <GitHubIcon className="h-3.5 w-3.5" />
              Star on GitHub
            </a>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 md:col-span-3">
            {COLUMNS.map((col) => (
              <div key={col.title}>
                <h2 className="text-[13px] font-semibold text-ink">{col.title}</h2>
                <ul className="mt-4 space-y-3">
                  {col.links.map((l) => (
                    <li key={l.label}>
                      {l.internal ? (
                        <Link to={l.href} className={linkClass}>{l.label}</Link>
                      ) : (
                        <a href={l.href} target="_blank" rel="noopener noreferrer" className={linkClass}>
                          {l.label}
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-12 flex flex-col gap-2 border-t border-hairline pt-6 text-[13px] text-steel sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Jithin. Not affiliated with Telegram FZ-LLC.</p>
          {version && <p>Latest release {version}</p>}
        </div>
      </div>
    </footer>
  )
}
