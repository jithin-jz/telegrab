import {
  Bookmark,
  Check,
  CircleArrowUp,
  FileText,
  Folder,
  Image as ImageIcon,
  LayoutGrid,
  Lock,
  Music,
  Play,
  Search,
} from 'lucide-react'

// Illustration of the desktop app's file explorer. Decorative only.

const SIDEBAR = [
  { icon: Bookmark, label: 'Saved Messages', active: true },
  { icon: Folder, label: 'Photos' },
  { icon: Folder, label: 'Projects' },
  { icon: Folder, label: 'Movies' },
  { icon: Lock, label: 'Vault' },
]

const FILES = [
  { name: 'Iceland trip.mp4', meta: '1.8 GB', kind: 'video', tint: 'from-[#4a36b0] to-[#7c5cff]' },
  { name: 'Design system.pdf', meta: '24 MB', kind: 'doc', tint: 'from-[#7a2d4d] to-[#ff6ec7]' },
  { name: 'Sunset.raw', meta: '58 MB', kind: 'image', tint: 'from-[#8a4a2c] to-[#ff8557]' },
  { name: 'Album master.flac', meta: '312 MB', kind: 'audio', tint: 'from-[#1f5f5c] to-[#4cb8b3]' },
  { name: 'Lecture 04.mkv', meta: '940 MB', kind: 'video', tint: 'from-[#2d4a8a] to-[#5b8def]' },
  { name: 'Contracts.zip', meta: '6 MB', kind: 'doc', tint: 'from-[#3a3a42] to-[#6b6b78]' },
] as const

const KIND_ICON = { video: Play, doc: FileText, image: ImageIcon, audio: Music }

export function AppMockup() {
  return (
    <div
      aria-hidden="true"
      className="relative overflow-hidden rounded-2xl border border-hairline-strong bg-surface shadow-[0_40px_120px_-30px_rgba(137,180,250,0.3),0_0_0_1px_rgba(255,255,255,0.02)]"
    >
      {/* Title bar */}
      <div className="flex h-10 items-center gap-2 border-b border-hairline bg-surface-2 px-4">
        <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
        <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
        <span className="h-3 w-3 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-[12px] font-medium text-steel">Telegrab</span>
      </div>

      <div className="flex min-h-[340px] sm:min-h-[400px]">
        {/* Sidebar */}
        <div className="hidden w-[190px] shrink-0 flex-col gap-0.5 border-r border-hairline p-3 sm:flex">
          <p className="px-2.5 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-steel">Library</p>
          {SIDEBAR.map(({ icon: Icon, label, active }) => (
            <div
              key={label}
              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12.5px] ${
                active ? 'bg-primary-soft text-ink' : 'text-slate'
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${active ? 'text-primary-ink' : ''}`} />
              {label}
            </div>
          ))}
          <div className="mt-auto rounded-lg border border-hairline bg-surface-2 p-3">
            <p className="text-[11px] text-steel">Storage used</p>
            <p className="mt-1 text-[13px] font-semibold text-ink">
              412 GB <span className="font-normal text-steel">of unlimited</span>
            </p>
          </div>
        </div>

        {/* Main */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-3 border-b border-hairline px-4 py-3">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-hairline bg-canvas px-3 py-1.5 text-[12px] text-steel">
              <Search className="h-3.5 w-3.5" />
              Search files
              <span className="ml-auto rounded border border-hairline px-1.5 text-[10px]">Ctrl K</span>
            </div>
            <LayoutGrid className="h-4 w-4 text-slate" />
          </div>

          <div className="grid flex-1 grid-cols-2 gap-3 p-4 md:grid-cols-3">
            {FILES.map((f, i) => {
              const Icon = KIND_ICON[f.kind]
              return (
                <div key={f.name} className={`rounded-xl border border-hairline bg-surface-2 p-2 ${i > 3 ? 'hidden md:block' : ''}`}>
                  <div className={`flex h-16 items-center justify-center rounded-lg bg-gradient-to-br sm:h-20 ${f.tint}`}>
                    <Icon className="h-5 w-5 text-white/85" />
                  </div>
                  <p className="mt-2 truncate px-0.5 text-[11.5px] font-medium text-ink">{f.name}</p>
                  <p className="px-0.5 text-[10.5px] text-steel">{f.meta}</p>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Transfer queue card */}
      <div className="absolute bottom-4 right-4 w-[220px] rounded-xl border border-hairline-strong bg-surface-3/95 p-3 shadow-2xl backdrop-blur sm:w-[260px]">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-ink">
          <CircleArrowUp className="h-4 w-4 text-primary-ink" />
          Uploading 2 files
        </div>
        <div className="mt-3 space-y-2.5">
          <div>
            <div className="flex justify-between text-[11px]">
              <span className="truncate text-slate">Iceland trip.mp4</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="progress-anim h-full rounded-full bg-gradient-to-r from-primary to-[#b4befe]" />
            </div>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="truncate text-slate">Album master.flac</span>
            <Check className="h-3.5 w-3.5 text-success" />
          </div>
        </div>
      </div>
    </div>
  )
}
