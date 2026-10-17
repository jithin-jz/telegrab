import { Link, NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Download, Menu, Star, X } from 'lucide-react'
import { REPO, REPO_URL, useDownloadUrl } from '../hooks/useDownloadUrl'
import { GitHubIcon, Logo } from './ui'

const LINKS = [
  { to: '/#features', label: 'Features' },
  { to: '/#how-it-works', label: 'How it works' },
  { to: '/#faq', label: 'FAQ' },
  { to: '/docs', label: 'Docs' },
]

export function Navbar() {
  const [stars, setStars] = useState<number | null>(null)
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const { url, label } = useDownloadUrl()

  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (typeof d?.stargazers_count === 'number') setStars(d.stargazers_count) })
      .catch(() => {})
  }, [])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const close = () => setOpen(false)

  return (
    <header
      className={`sticky top-0 z-50 border-b transition-colors duration-300 ${
        scrolled || open
          ? 'border-hairline bg-canvas/80 backdrop-blur-xl'
          : 'border-transparent bg-transparent'
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-5 sm:px-6" aria-label="Main">
        <Link to="/" onClick={close} className="flex items-center gap-2.5" aria-label="Telegrab home">
          <Logo />
          <span className="text-[16px] font-semibold tracking-[-0.01em] text-ink">Telegrab</span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end
              className={({ isActive }) =>
                `rounded-full px-3.5 py-2 text-[14px] font-medium transition-colors ${
                  isActive && !l.to.includes('#') ? 'text-ink' : 'text-slate hover:text-ink'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-full px-3 py-2 text-[14px] font-medium text-slate transition-colors hover:text-ink"
          >
            <GitHubIcon />
            {stars !== null && (
              <span className="flex items-center gap-1 tabular-nums">
                <Star className="h-3.5 w-3.5" aria-hidden="true" />
                {stars.toLocaleString()}
              </span>
            )}
            <span className="sr-only">GitHub repository</span>
          </a>
          <a
            href={url}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-[14px] font-semibold text-canvas transition hover:bg-white active:scale-[0.98]"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {label.replace('Download for ', '')}
          </a>
        </div>

        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="-mr-2 flex h-10 w-10 items-center justify-center rounded-full text-ink md:hidden"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          aria-controls="mobile-menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {open && (
        <div id="mobile-menu" className="border-t border-hairline px-5 pb-6 pt-3 md:hidden">
          <div className="flex flex-col">
            {LINKS.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={close}
                className="border-b border-hairline py-3.5 text-[16px] font-medium text-ink"
              >
                {l.label}
              </Link>
            ))}
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 border-b border-hairline py-3.5 text-[16px] font-medium text-ink"
            >
              <GitHubIcon /> GitHub{stars !== null && <span className="text-slate">· {stars.toLocaleString()} stars</span>}
            </a>
            <a
              href={url}
              className="mt-5 inline-flex items-center justify-center gap-2 rounded-full bg-primary px-5 py-3 text-[15px] font-semibold text-canvas"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              {label}
            </a>
          </div>
        </div>
      )}
    </header>
  )
}
