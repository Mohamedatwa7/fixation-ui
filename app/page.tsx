import Link from 'next/link'
import StreamHero from '@/components/landing/StreamHero'

export default function LandingPage() {
  return (
    <main className="bg-noir text-[#fafafa]">
      {/* ── Hero (perspective corridor of diagnosed creatives) ── */}
      <StreamHero />

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
            <span className="text-white/40">Measure it.</span>
          </h2>
          <Link
            href="/upload"
            className="group mt-10 inline-flex items-center gap-3 bg-accent text-[#0a0a0a] font-mono text-[11px]
                       font-medium uppercase tracking-[0.18em] px-8 py-4 rounded-[3px]
                       hover:bg-white transition-colors duration-300 ease-cinematic
                       shadow-[0_0_40px_-8px_rgba(224,224,224,0.35)]"
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
