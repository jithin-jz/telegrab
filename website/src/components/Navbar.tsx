import { Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'

export function Navbar() {
  const { pathname } = useLocation()
  const [stars, setStars] = useState<number | null>(null)

  useEffect(() => {
    fetch('https://api.github.com/repos/jithin-jz/telegrab')
      .then(r => r.json())
      .then(d => { if (d.stargazers_count != null) setStars(d.stargazers_count) })
      .catch(() => {})
  }, [])

  return (
    <nav className="sticky top-0 z-50 border-b border-hairline-dark bg-canvas">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/logo.svg" alt="Telegrab" className="h-6 w-6" />
          <span className="text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary">
            Telegrab
          </span>
        </Link>

        <div className="flex items-center gap-8">
          <Link
            to="/"
            className={`text-[12px] uppercase tracking-[0.96px] transition-opacity ${pathname === '/' ? 'text-on-primary' : 'text-on-primary/60 hover:text-on-primary'}`}
          >
            Home
          </Link>
          <Link
            to="/docs"
            className={`text-[12px] uppercase tracking-[0.96px] transition-opacity ${pathname === '/docs' ? 'text-on-primary' : 'text-on-primary/60 hover:text-on-primary'}`}
          >
            Docs
          </Link>
          <a
            href="https://github.com/jithin-jz/telegrab"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-[32px] border border-on-primary/30 px-3 py-1.5 text-[11px] uppercase tracking-[0.96px] text-on-primary/80 transition-colors hover:border-on-primary hover:text-on-primary"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
            Star{stars !== null && <span className="ml-1 text-on-primary/60">·</span>}{stars !== null && <span className="ml-1">{stars}</span>}
          </a>
          <a
            href="https://github.com/jithin-jz/telegrab/releases/latest"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-[32px] border border-on-primary px-4 py-2 text-[11px] font-bold uppercase tracking-[1.17px] text-on-primary transition-all active:scale-95 hover:bg-on-primary hover:text-canvas"
          >
            Download
          </a>
        </div>
      </div>
    </nav>
  )
}
