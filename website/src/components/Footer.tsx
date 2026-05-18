export function Footer() {
  return (
    <footer className="border-t border-hairline-dark bg-canvas">
      <div className="mx-auto max-w-[1200px] px-8 py-12">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div>
            <h4 className="text-[12px] font-bold uppercase tracking-[0.96px] text-on-primary">Product</h4>
            <ul className="mt-4 space-y-3 text-[13px] text-on-primary-mute tracking-[0]">
              <li><a href="https://github.com/jithin-jz/telegrab/releases/latest" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">Download</a></li>
              <li><a href="https://github.com/jithin-jz/telegrab" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">Source Code</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[12px] font-bold uppercase tracking-[0.96px] text-on-primary">Resources</h4>
            <ul className="mt-4 space-y-3 text-[13px] text-on-primary-mute tracking-[0]">
              <li><a href="/docs" className="hover:text-on-primary underline transition-colors">Documentation</a></li>
              <li><a href="https://github.com/jithin-jz/telegrab/issues" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">Issues</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[12px] font-bold uppercase tracking-[0.96px] text-on-primary">Developer</h4>
            <ul className="mt-4 space-y-3 text-[13px] text-on-primary-mute tracking-[0]">
              <li><a href="https://github.com/jithin-jz" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">GitHub</a></li>
              <li><a href="https://www.linkedin.com/in/jithin-kr" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">LinkedIn</a></li>
              <li><a href="https://www.instagram.com/jithin.jz/" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">Instagram</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[12px] font-bold uppercase tracking-[0.96px] text-on-primary">Legal</h4>
            <ul className="mt-4 space-y-3 text-[13px] text-on-primary-mute tracking-[0]">
              <li><a href="https://github.com/jithin-jz/telegrab/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:text-on-primary underline transition-colors">MIT License</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-hairline-dark pt-6">
          <p className="text-[13px] text-on-primary-mute tracking-[0]">
            © 2026 Jithin. Not affiliated with Telegram FZ-LLC.
          </p>
        </div>
      </div>
    </footer>
  )
}
