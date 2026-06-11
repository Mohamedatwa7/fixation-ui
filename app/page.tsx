import Link from 'next/link'
import Nav from '@/components/Nav'

export default function LandingPage() {
  return (
    <main className="bg-noir text-[#fafafa]">
      <Nav />

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section
        className="relative min-h-screen flex items-center justify-center pt-16 overflow-hidden"
        aria-label="Hero"
      >
        {/* Layered backdrops */}
        <div className="absolute inset-0 bg-grid" aria-hidden="true" />
        <div className="absolute inset-0 spotlight" aria-hidden="true" />
        <div
          className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-noir to-transparent"
          aria-hidden="true"
        />

        <div className="relative z-10 w-full max-w-3xl mx-auto px-6 flex flex-col items-center text-center">

          {/* Status eyebrow */}
          <div
            className="flex items-center gap-2.5 mb-10 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.03] animate-rise"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" aria-hidden="true" />
            <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/55">
              Diagnostic engine · online
            </span>
          </div>

          {/* Wordmark */}
          <p
            className="font-mono font-bold leading-none tracking-tightest select-none text-[#fafafa] animate-rise"
            style={{ fontSize: 'clamp(4.5rem, 16vw, 11rem)', animationDelay: '0.06s' }}
            aria-label="F1X8"
          >
            F<span className="text-accent">1</span>X<span className="text-accent">8</span>
          </p>

          {/* Headline */}
          <h1
            className="font-mono font-semibold leading-[1.05] tracking-tightest text-[#fafafa] mt-8 animate-rise"
            style={{ fontSize: 'clamp(1.5rem, 4vw, 2.75rem)', animationDelay: '0.12s' }}
          >
            See what your audience sees,{' '}
            <span className="text-accent">before they do.</span>
          </h1>

          {/* Sub-line */}
          <p
            className="font-sans text-base md:text-lg text-white/50 leading-relaxed mt-7 max-w-xl animate-rise"
            style={{ animationDelay: '0.16s' }}
          >
            Cognitive-science attention diagnostics for video and static creative —
            grounded in real gaze data, calibrated against 30,000 ads.
          </p>

          {/* CTA */}
          <div
            className="mt-11 flex flex-col items-center gap-5 animate-rise"
            style={{ animationDelay: '0.24s' }}
          >
            <Link
              href="/upload"
              className="group inline-flex items-center gap-3 bg-accent text-[#0a0a0a] font-mono text-[11px]
                         font-medium uppercase tracking-[0.18em] px-8 py-4 rounded-[3px]
                         hover:bg-[#ff6a44] transition-colors duration-300 ease-cinematic
                         shadow-[0_0_40px_-8px_rgba(255,79,35,0.6)]"
            >
              Run a diagnostic
              <ArrowRight />
            </Link>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/35">
              No account required · Results in &lt; 30s
            </span>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-9 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2" aria-hidden="true">
          <span className="font-mono text-[9px] tracking-[0.25em] uppercase text-white/30">Scroll</span>
          <svg width="12" height="14" viewBox="0 0 12 14" fill="none">
            <path d="M6 1v12M2 9l4 4 4-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className="text-white/30" />
          </svg>
        </div>
      </section>

      {/* ── Method grid ──────────────────────────────────────── */}
      <section className="relative border-t border-white/10 bg-noir" aria-label="Why F1X8">
        <div className="max-w-5xl mx-auto px-6 py-20 md:py-28">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-14 text-center">
            ── The Method ──
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-white/10 border border-white/10 rounded-[3px] overflow-hidden">
            {groundingItems.map(item => (
              <article
                key={item.label}
                className="flex flex-col items-center text-center bg-noir px-6 py-10 hover:bg-panel transition-colors duration-300"
              >
                <span className="font-mono text-xs tracking-[0.2em] text-accent mb-5">
                  {item.numeral}
                </span>
                <h3 className="font-mono text-base font-semibold tracking-tight text-[#fafafa] mb-3">
                  {item.label}
                </h3>
                <p className="font-sans text-[13px] text-white/50 leading-relaxed">
                  {item.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Closing CTA ──────────────────────────────────────── */}
      <section className="relative border-t border-white/10 overflow-hidden" aria-label="Get started">
        <div className="absolute inset-0 bg-dots opacity-60" aria-hidden="true" />
        <div className="relative max-w-3xl mx-auto px-6 py-24 md:py-32 flex flex-col items-center text-center">
          <h2
            className="font-mono font-semibold leading-[1.08] tracking-tightest text-[#fafafa]"
            style={{ fontSize: 'clamp(1.75rem, 4.5vw, 3.25rem)' }}
          >
            Stop guessing what gets seen.{' '}
            <span className="text-accent">Measure it.</span>
          </h2>
          <Link
            href="/upload"
            className="group mt-10 inline-flex items-center gap-3 bg-accent text-[#0a0a0a] font-mono text-[11px]
                       font-medium uppercase tracking-[0.18em] px-8 py-4 rounded-[3px]
                       hover:bg-[#ff6a44] transition-colors duration-300 ease-cinematic
                       shadow-[0_0_40px_-8px_rgba(255,79,35,0.6)]"
          >
            Run a diagnostic
            <ArrowRight />
          </Link>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="border-t border-white/10 px-6 md:px-10 py-8">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="font-mono text-xs tracking-tightest text-white/60">
            F<span className="text-accent">1</span>X<span className="text-accent">8</span>
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/30">
            © 2025 — All rights reserved
          </span>
        </div>
      </footer>
    </main>
  )
}

/* ── Icons ────────────────────────────────────────────────────── */

function ArrowRight() {
  return (
    <svg width="16" height="12" viewBox="0 0 16 12" fill="none" aria-hidden="true"
      className="transition-transform duration-300 ease-cinematic group-hover:translate-x-1">
      <path d="M1 6h13M10 1l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/* ── Data ─────────────────────────────────────────────────────── */

const groundingItems = [
  {
    numeral: 'I',
    label: 'Real gaze data',
    description: 'Trained on 200,000+ eye-tracking sessions from real viewers in controlled studies.',
  },
  {
    numeral: 'II',
    label: 'Cited research',
    description: 'Every metric is grounded in peer-reviewed cognitive science — no black-box scoring.',
  },
  {
    numeral: 'III',
    label: '30K-ad benchmark',
    description: 'Each score is calibrated against a library of 30,000 analyzed advertisements.',
  },
  {
    numeral: 'IV',
    label: 'Arabic & Urdu',
    description: 'Right-to-left reading-path models built for MENA and South Asian markets.',
  },
]
