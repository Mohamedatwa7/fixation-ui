import Link from 'next/link'

interface NavProps {
  active?: 'upload' | 'results'
  /** Transparent, logo-only nav that blends into the page (landing) */
  minimal?: boolean
}

export default function Nav({ active, minimal }: NavProps) {
  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 md:px-10
        ${minimal ? 'bg-transparent' : 'border-b border-white/10 bg-[#0a0a0a]/85 backdrop-blur-md'}`}
      aria-label="Main navigation"
    >
      <Link
        href="/"
        className="font-mono text-base font-semibold tracking-tightest text-[#fafafa] hover:opacity-70 transition-opacity duration-300"
        aria-label="F1X8 — home"
      >
        F<span className="text-accent">1</span>X<span className="text-accent">8</span>
      </Link>

      {!minimal && (
      <div className="flex items-center gap-7">
        {active === 'results' && (
          <Link
            href="/upload"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 hover:text-white/80 transition-colors duration-300"
          >
            New diagnostic
          </Link>
        )}
        <Link
          href="/upload"
          className={`font-mono text-[10px] uppercase tracking-[0.18em] px-4 py-2 rounded-[2px] transition-colors duration-300
            ${active === 'upload'
              ? 'bg-accent text-[#0a0a0a]'
              : 'border border-white/15 text-white/60 hover:border-accent hover:text-accent'
            }`}
        >
          Run a diagnostic
        </Link>
      </div>
      )}
    </nav>
  )
}
