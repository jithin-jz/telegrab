import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

export function Home() {
  return (
    <>
      {/* Hero — dark tile */}
      <section className="bg-surface-dark text-on-dark">
        <div className="mx-auto max-w-[980px] px-6 py-20 text-center">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="font-display text-[56px] font-semibold leading-[1.07] tracking-[-0.28px] sm:text-[56px]">
              Your Telegram.{' '}
              <br className="hidden sm:block" />
              Unlimited Storage.
            </h1>
            <p className="mx-auto mt-4 max-w-[600px] text-[21px] font-normal leading-[1.19] tracking-[0.231px] text-body-muted">
              Telegrab turns your Telegram account into unlimited, private cloud storage. No caps, no subscription fees.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <a
                href="https://github.com/jithin-jz/telegrab/releases/latest"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full bg-primary-on-dark px-[22px] py-[11px] text-[17px] font-normal text-on-dark tracking-[-0.374px] transition-transform active:scale-95"
              >
                Download for Free
              </a>
              <Link
                to="/docs"
                className="text-[17px] font-normal text-primary-on-dark tracking-[-0.374px] transition-opacity hover:opacity-80"
              >
                Learn more →
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features — light tile */}
      <section className="bg-canvas">
        <div className="mx-auto max-w-[980px] px-6 py-20 text-center">
          <h2 className="font-display text-[40px] font-semibold leading-[1.1] text-ink">
            Everything you need.
          </h2>
          <p className="mt-2 text-[21px] font-normal leading-[1.19] tracking-[0.231px] text-ink-subtle">
            A complete cloud storage solution built on Telegram.
          </p>

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

      {/* Tech — parchment tile */}
      <section className="bg-parchment">
        <div className="mx-auto max-w-[980px] px-6 py-20 text-center">
          <h2 className="font-display text-[40px] font-semibold leading-[1.1] text-ink">
            Built for performance.
          </h2>
          <p className="mt-2 text-[21px] font-normal leading-[1.19] tracking-[0.231px] text-ink-subtle">
            Modern stack. Native feel.
          </p>
          <div className="mt-12 grid gap-6 sm:grid-cols-3">
            <TechCard label="Frontend" value="React 18, TypeScript, Tailwind CSS" />
            <TechCard label="Backend" value="Python 3.11+, Telethon (MTProto), FastAPI" />
            <TechCard label="Desktop" value="pywebview (WebView2 / WebKit)" />
          </div>
        </div>
      </section>

      {/* CTA — dark tile */}
      <section className="bg-surface-dark-2 text-on-dark">
        <div className="mx-auto max-w-[980px] px-6 py-20 text-center">
          <h2 className="font-display text-[40px] font-semibold leading-[1.1]">
            Ready to get started?
          </h2>
          <p className="mt-2 text-[21px] font-normal leading-[1.19] tracking-[0.231px] text-body-muted">
            Download Telegrab and start using your unlimited cloud storage today.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <a
              href="https://github.com/jithin-jz/telegrab/releases/latest"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full bg-primary-on-dark px-[22px] py-[11px] text-[17px] font-normal text-on-dark tracking-[-0.374px] transition-transform active:scale-95"
            >
              Download Now
            </a>
            <a
              href="https://github.com/jithin-jz/telegrab"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[17px] font-normal text-primary-on-dark tracking-[-0.374px] transition-opacity hover:opacity-80"
            >
              View on GitHub →
            </a>
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
    >
      <h3 className="text-[17px] font-semibold text-ink leading-[1.24] tracking-[-0.374px]">{title}</h3>
      <p className="mt-1 text-[14px] font-normal text-ink-subtle leading-[1.43] tracking-[-0.224px]">{desc}</p>
    </motion.div>
  )
}

function TechCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[18px] border border-hairline bg-canvas p-6 text-left">
      <p className="text-[14px] font-semibold text-ink tracking-[-0.224px]">{label}</p>
      <p className="mt-1 text-[14px] text-ink-subtle leading-[1.43] tracking-[-0.224px]">{value}</p>
    </div>
  )
}
