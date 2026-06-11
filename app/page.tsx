import Link from 'next/link'
import Nav from '@/components/Nav'

export default function LandingPage() {
  return (
    <main className="bg-paper text-ink">
      <Nav theme="light" />

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section
        className="bg-grid-light relative min-h-screen flex flex-col justify-center pt-16"
        aria-label="Hero"
      >
        <div className="max-w-6xl w-full mx-auto px-6 md:px-10">

          {/* Eyebrow / wordmark */}
          <div className="flex items-center gap-4 mb-10 animate-rise">
            <span className="font-mono text-sm font-semibold tracking-tightest text-ink">
              F<span className="text-accent">1</span>X<span className="text-accent">8</span>
            </span>
            <span className="h-px flex-1 max-w-[80px] bg-ink/15" aria-hidden="true" />
            <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink/45">
              Creative Diagnostics
            </span>
          </div>

          {/* Headline */}
          <h1
            className="font-serif font-normal text-ink leading-[1.02] tracking-tightest max-w-4xl
                       animate-rise"
            style={{ fontSize: 'clamp(2.75rem, 7vw, 6.5rem)', animationDelay: '0.08s' }}
          >
            See what your audience sees,{' '}
            <span className="italic text-accent">before they do.</span>
          </h1>

          {/* Sub-line */}
          <p
            className="prose-serif text-ink/55 mt-8 max-w-xl animate-rise"
            style={{ fontSize: 'clamp(1.05rem, 1.6vw, 1.35rem)', animationDelay: '0.16s' }}
          >
            A cognitive-science approach to attention — diagnostics for video and
            static creative, grounded in real gaze data.
          </p>

          {/* CTA row */}
          <div
            className="mt-12 flex flex-wrap items-center gap-6 animate-rise"
            style={{ animationDelay: '0.24s' }}
          >
            <Link
              href="/upload"
              className="group inline-flex items-center gap-3 bg-ink text-paper font-mono text-[11px]
                         uppercase tracking-[0.18em] px-8 py-4 rounded-[2px]
                         hover:bg-accent transition-colors duration-300 ease-cinematic"
            >
              Run a diagnostic
              <ArrowRight />
            </Link>
            <span className="font-mono text-[11px] tracking-wide text-ink/40">
              No account required · Results in &lt; 30s
            </span>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-10 left-6 md:left-10 flex items-center gap-3" aria-hidden="true">
          <span className="font-mono text-[9px] tracking-[0.25em] uppercase text-ink/35">Scroll</span>
          <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
            <path d="M1 1l6 6 6-6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className="text-ink/35" />
          </svg>
        </div>
      </section>

      {/* ── Grounding strip ──────────────────────────────────── */}
      <section className="border-t border-ink/10 bg-paper" aria-label="Why F1X8">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-20 md:py-28">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink/40 mb-12">
            The Method
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            {groundingItems.map((item, i) => (
              <article
                key={item.label}
                className={`flex flex-col py-8 lg:py-0 lg:px-10 first:lg:pl-0 last:lg:pr-0
                  ${i > 0 ? 'border-t sm:border-t-0 sm:[&:nth-child(odd)]:border-l-0 lg:border-l border-ink/10' : ''}`}
              >
                <span className="font-mono text-[11px] tracking-[0.2em] text-accent mb-5">
                  {item.numeral}
                </span>
                <h3 className="font-serif text-2xl md:text-[1.75rem] leading-tight text-ink mb-3">
                  {item.label}
                </h3>
                <p className="prose-serif text-[0.95rem] text-ink/55">
                  {item.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Closing CTA band ─────────────────────────────────── */}
      <section className="border-t border-ink/10 bg-ink text-paper" aria-label="Get started">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-24 md:py-32 flex flex-col items-start">
          <h2
            className="font-serif font-normal leading-[1.05] tracking-tightest max-w-3xl"
            style={{ fontSize: 'clamp(2rem, 5vw, 4rem)' }}
          >
            Stop guessing what gets seen.{' '}
            <span className="italic text-accent">Measure it.</span>
          </h2>
          <Link
            href="/upload"
            className="group mt-10 inline-flex items-center gap-3 bg-paper text-ink font-mono text-[11px]
                       uppercase tracking-[0.18em] px-8 py-4 rounded-[2px]
                       hover:bg-accent hover:text-paper transition-colors duration-300 ease-cinematic"
          >
            Run a diagnostic
            <ArrowRight />
          </Link>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="bg-ink text-paper border-t border-white/10 px-6 md:px-10 py-8">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <span className="font-mono text-xs tracking-tightest text-paper/70">
            F<span className="text-accent">1</span>X<span className="text-accent">8</span>
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-paper/35">
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
      <path d="M1 6h13M10 1l5 5-5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
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
