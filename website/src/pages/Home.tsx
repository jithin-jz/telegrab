import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

export function Home() {
  return (
    <>
      {/* Hero — full viewport band */}
      <section className="relative flex min-h-screen items-center justify-center bg-canvas">
        <div className="relative z-10 text-center px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h1 className="font-display text-[80px] font-bold uppercase leading-[0.95] tracking-[1.6px] text-on-primary sm:text-[80px] max-[768px]:text-[48px]">
              UNLIMITED
              <br />
              STORAGE
            </h1>
            <p className="mx-auto mt-6 max-w-[500px] text-[16px] leading-[1.7] tracking-[0.32px] text-on-primary-mute">
              Telegrab turns your Telegram account into unlimited, private cloud storage. No caps, no subscription fees.
            </p>
            <div className="mt-10">
              <a
                href="https://github.com/jithin-jz/telegrab/releases/latest"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block rounded-[32px] border border-on-primary px-6 py-[18px] text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary transition-all active:scale-95 hover:bg-on-primary hover:text-canvas"
              >
                Download Now
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features — dark soft band */}
      <section className="bg-canvas-soft border-t border-hairline-dark">
        <div className="mx-auto max-w-[1200px] px-8 py-24 text-center">
          <h2 className="font-display text-[60px] font-bold uppercase leading-[1.2] tracking-[1.2px] text-on-primary max-[768px]:text-[40px]">
            EVERYTHING YOU NEED
          </h2>

          <div className="mt-16 grid gap-12 text-left sm:grid-cols-2 lg:grid-cols-3">
            <Feature title="Unlimited Storage" desc="Powered by Telegram's cloud infrastructure. No storage limits, no subscription fees." />
            <Feature title="File Explorer" desc="Full-featured UI with drag & drop, folders, and list/grid views." />
            <Feature title="Media Streaming" desc="Watch 4K videos or listen to audio instantly without full downloads." />
            <Feature title="Privacy First" desc="Files stay between you and Telegram. No third-party servers involved." />
            <Feature title="Developer API" desc="Optional REST API for automations and LLM integrations." />
            <Feature title="Cross Platform" desc="Available for Windows and macOS. Open source and MIT licensed." />
          </div>
        </div>
      </section>

      {/* Tech — dark band */}
      <section className="bg-canvas border-t border-hairline-dark">
        <div className="mx-auto max-w-[1200px] px-8 py-24 text-center">
          <h2 className="font-display text-[48px] font-bold uppercase leading-[1.25] tracking-[0.96px] text-on-primary max-[768px]:text-[32px]">
            BUILT FOR PERFORMANCE
          </h2>
          <div className="mt-12 grid gap-6 sm:grid-cols-3">
            <TechCard label="Frontend" value="React 18, TypeScript, Tailwind CSS" />
            <TechCard label="Backend" value="Python 3.11+, Telethon (MTProto), FastAPI" />
            <TechCard label="Desktop" value="pywebview (WebView2 / WebKit)" />
          </div>
        </div>
      </section>

      {/* CTA — dark band */}
      <section className="bg-canvas-soft border-t border-hairline-dark">
        <div className="mx-auto max-w-[1200px] px-8 py-24 text-center">
          <h2 className="font-display text-[60px] font-bold uppercase leading-[1.2] tracking-[1.2px] text-on-primary max-[768px]:text-[40px]">
            GET STARTED
          </h2>
          <p className="mt-4 text-[16px] leading-[1.7] tracking-[0.32px] text-on-primary-mute">
            Download Telegrab and start using your unlimited cloud storage today.
          </p>
          <div className="mt-10 flex flex-col items-center gap-6 sm:flex-row sm:justify-center">
            <a
              href="https://github.com/jithin-jz/telegrab/releases/latest"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-[32px] border border-on-primary px-6 py-[18px] text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary transition-all active:scale-95 hover:bg-on-primary hover:text-canvas"
            >
              Download
            </a>
            <Link
              to="/docs"
              className="rounded-[32px] border border-on-primary/40 px-6 py-[18px] text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary transition-all active:scale-95 hover:border-on-primary"
            >
              Installation Guide
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}

function Feature({ title, desc }: { title: string; desc: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="border-t border-hairline-dark pt-6"
    >
      <h3 className="text-[13px] font-bold uppercase tracking-[1.17px] text-on-primary">{title}</h3>
      <p className="mt-2 text-[16px] leading-[1.7] tracking-[0.32px] text-on-primary-mute">{desc}</p>
    </motion.div>
  )
}

function TechCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-hairline-dark rounded-[8px] p-6 text-left">
      <p className="text-[12px] font-bold uppercase tracking-[0.96px] text-on-primary-mute">{label}</p>
      <p className="mt-2 text-[16px] leading-[1.5] tracking-[0.32px] text-on-primary">{value}</p>
    </div>
  )
}
