import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { Navbar } from './components/Navbar'
import { Footer } from './components/Footer'
import { btnSecondary } from './components/ui'
import { Home } from './pages/Home'
import { Docs } from './pages/Docs'

const TITLES: Record<string, string> = {
  '/': 'Telegrab: Unlimited Cloud Storage on Telegram',
  '/docs': 'Installation Guide · Telegrab',
}

export default function App() {
  const { pathname, hash } = useLocation()

  // Scroll to the #section in the URL (also when arriving from another page),
  // otherwise start each page at the top.
  useEffect(() => {
    document.title = TITLES[pathname] ?? 'Page not found · Telegrab'
    if (hash) {
      const el = document.getElementById(decodeURIComponent(hash.slice(1)))
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' })
        return
      }
    }
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname, hash])

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only z-[60] rounded-full bg-primary px-4 py-2 text-[14px] font-semibold text-canvas focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <Navbar />
      <main id="main" className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}

function NotFound() {
  return (
    <section className="mx-auto flex max-w-[560px] flex-col items-center px-5 py-32 text-center">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-primary-ink">404</p>
      <h1 className="mt-3 text-[36px] font-semibold tracking-[-0.02em] text-ink">Page not found</h1>
      <p className="mt-3 text-[16px] text-slate">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className={`${btnSecondary} mt-8`}>
        Back to home
      </Link>
    </section>
  )
}
