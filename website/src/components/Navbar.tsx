import { Link, useLocation } from 'react-router-dom'

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
    </svg>
  )
}

export function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav className="sticky top-0 z-50 border-b border-white/5 bg-canvas/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/icon.png" alt="Telegrab" className="h-8 w-8" />
          <span className="text-lg font-bold tracking-tight">Telegrab</span>
        </Link>

        <div className="flex items-center gap-8">
          <Link
            to="/"
            className={`text-sm font-medium transition-colors ${pathname === '/' ? 'text-ink' : 'text-ink-muted hover:text-ink'}`}
          >
            Home
          </Link>
          <Link
            to="/docs"
            className={`text-sm font-medium transition-colors ${pathname === '/docs' ? 'text-ink' : 'text-ink-muted hover:text-ink'}`}
          >
            Docs
          </Link>
          <a
            href="https://github.com/jithin-jz/telegrab"
            target="_blank"
            rel="noopener noreferrer"
            className="text-ink-muted hover:text-ink transition-colors"
          >
            <GithubIcon className="h-5 w-5" />
          </a>
          <a
            href="https://github.com/jithin-jz/telegrab/releases/latest"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-hover"
          >
            Download
          </a>
        </div>
      </div>
    </nav>
  )
}
