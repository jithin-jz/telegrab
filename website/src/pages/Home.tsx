import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Download, HardDrive, Film, Shield, Code, FolderOpen } from 'lucide-react'

const features = [
  { icon: HardDrive, title: 'Unlimited Storage', desc: 'Powered by Telegram\'s cloud infrastructure. No storage limits, no subscription fees.' },
  { icon: FolderOpen, title: 'File Explorer', desc: 'Full-featured UI with drag & drop, folders, and list/grid views.' },
  { icon: Film, title: 'Media Streaming', desc: 'Watch 4K videos or listen to audio instantly without full downloads.' },
  { icon: Shield, title: 'Privacy First', desc: 'Files stay between you and Telegram. No third-party servers involved.' },
  { icon: Code, title: 'Developer Ready', desc: 'Optional REST API for automations and LLM integrations.' },
]

export function Home() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,92,252,0.15),transparent_60%)]" />
        <div className="relative mx-auto max-w-6xl px-6 pt-24 pb-20 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5">
              <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
              <span className="text-xs font-medium text-ink-muted">v1.4.0 — Now with in-app updates</span>
            </div>

            <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl lg:text-7xl">
              Your Telegram.{' '}
              <span className="bg-gradient-to-r from-primary to-purple-400 bg-clip-text text-transparent">
                Unlimited Storage.
              </span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-muted leading-relaxed">
              Telegrab turns your Telegram account into unlimited, private cloud storage.
              No caps, no subscription fees — just your files on the cloud you already trust.
            </p>

            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <a
                href="https://github.com/jithin-jz/telegrab/releases/latest"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-primary/25 transition-all hover:bg-primary-hover hover:shadow-xl hover:shadow-primary/30 hover:-translate-y-0.5"
              >
                <Download className="h-5 w-5" />
                Download for Windows
              </a>
              <Link
                to="/docs"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-surface px-8 py-3.5 text-base font-semibold text-ink transition-all hover:bg-elevated hover:border-white/20"
              >
                Installation Guide
              </Link>
            </div>

            <p className="mt-4 text-xs text-slate">
              Available for Windows & macOS • MIT License • Open Source
            </p>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-white/5 bg-surface/30">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Everything you need</h2>
            <p className="mt-3 text-ink-muted">A complete cloud storage solution built on top of Telegram.</p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group rounded-2xl border border-white/5 bg-elevated/50 p-6 transition-all hover:border-primary/20 hover:bg-elevated"
              >
                <div className="mb-4 inline-flex rounded-xl bg-primary/10 p-3">
                  <f.icon className="h-5 w-5 text-primary" />
                </div>
                <h3 className="text-base font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-ink-muted leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-white/5">
        <div className="mx-auto max-w-6xl px-6 py-24 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Ready to get started?</h2>
          <p className="mt-3 text-ink-muted">Download Telegrab and start using your unlimited cloud storage today.</p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <a
              href="https://github.com/jithin-jz/telegrab/releases/latest"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-primary/25 transition-all hover:bg-primary-hover"
            >
              <Download className="h-5 w-5" />
              Download Now
            </a>
            <a
              href="https://github.com/jithin-jz/telegrab"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-surface px-8 py-3.5 text-base font-semibold text-ink transition-all hover:bg-elevated"
            >
              View on GitHub
            </a>
          </div>
        </div>
      </section>
    </>
  )
}
