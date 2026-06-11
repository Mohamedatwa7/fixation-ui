import Link from 'next/link'

interface NavProps {
  active?: 'upload' | 'results'
  /** Visual theme. Defaults to dark for results, light otherwise. */
  theme?: 'light' | 'dark'
}

export default function Nav({ active, theme }: NavProps) {
  const resolved = theme ?? (active === 'results' ? 'dark' : 'light')
  const dark = resolved === 'dark'

  const bar = dark
    ? 'border-white/10 bg-[#0b0b0a]/90'
    : 'border-ink/10 bg-paper/90'
  const wordmark = dark ? 'text-paper' : 'text-ink'
  const ghost = dark
    ? 'text-white/40 hover:text-white/80'
    : 'text-ink/40 hover:text-ink/80'
  const ctaActive = dark
    ? 'bg-accent text-[#0b0b0a]'
    : 'bg-ink text-paper'
  const ctaIdle = dark
    ? 'border border-white/15 text-white/60 hover:border-accent hover:text-accent'
    : 'border border-ink/15 text-ink/60 hover:border-accent hover:text-accent'

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 md:px-10 border-b backdrop-blur-md ${bar}`}
      aria-label="Main navigation"
    >
      <Link
        href="/"
        className={`font-mono text-base font-semibold tracking-tightest ${wordmark} hover:opacity-70 transition-opacity duration-300`}
        aria-label="F1X8 — home"
      >
        F<span className="text-accent">1</span>X<span className="text-accent">8</span>
      </Link>

      <div className="flex items-center gap-7">
        {active === 'results' && (
          <Link
            href="/upload"
            className={`font-mono text-[10px] uppercase tracking-[0.18em] transition-colors duration-300 ${ghost}`}
          >
            New diagnostic
          </Link>
        )}
        <Link
          href="/upload"
          className={`font-mono text-[10px] uppercase tracking-[0.18em] px-4 py-2 rounded-[2px] transition-colors duration-300
            ${active === 'upload' ? ctaActive : ctaIdle}`}
        >
          Run a diagnostic
        </Link>
      </div>
    </nav>
  )
}
