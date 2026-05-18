export function Footer() {
  return (
    <footer className="bg-parchment">
      <div className="mx-auto max-w-[980px] px-6 py-16">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div>
            <h4 className="text-[14px] font-semibold text-ink tracking-[-0.224px] leading-[1.29]">Product</h4>
            <ul className="mt-3 space-y-0 text-[12px] text-ink-subtle leading-[2.41]">
              <li><a href="https://github.com/jithin-jz/telegrab/releases/latest" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">Download</a></li>
              <li><a href="https://github.com/jithin-jz/telegrab" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">Source Code</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[14px] font-semibold text-ink tracking-[-0.224px] leading-[1.29]">Resources</h4>
            <ul className="mt-3 space-y-0 text-[12px] text-ink-subtle leading-[2.41]">
              <li><a href="/docs" className="hover:text-ink transition-colors">Documentation</a></li>
              <li><a href="https://github.com/jithin-jz/telegrab/issues" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">Issues</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[14px] font-semibold text-ink tracking-[-0.224px] leading-[1.29]">Developer</h4>
            <ul className="mt-3 space-y-0 text-[12px] text-ink-subtle leading-[2.41]">
              <li><a href="https://github.com/jithin-jz" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">GitHub</a></li>
              <li><a href="https://www.linkedin.com/in/jithin-kr" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">LinkedIn</a></li>
              <li><a href="https://www.instagram.com/jithin.jz/" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">Instagram</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[14px] font-semibold text-ink tracking-[-0.224px] leading-[1.29]">Legal</h4>
            <ul className="mt-3 space-y-0 text-[12px] text-ink-subtle leading-[2.41]">
              <li><a href="https://github.com/jithin-jz/telegrab/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">MIT License</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-hairline pt-4">
          <p className="text-[12px] text-ink-subtle tracking-[-0.12px]">
            © 2026 Jithin. Not affiliated with Telegram FZ-LLC.
          </p>
        </div>
      </div>
    </footer>
  )
}
