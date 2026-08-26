import Link from 'next/link'
import ImageStreamHero from '@/components/ui/image-stream-hero'

/**
 * Landing hero — a perspective corridor of ad creatives rushing past the
 * viewer (components/ui/image-stream-hero), dressed in the F1X8 console
 * aesthetic: silver-halide monochrome imagery, technical grid, film grain,
 * and the diagnostic-engine overlay chrome.
 */

// Campaign-style stock imagery — the corridor is decorative (aria-hidden),
// standing in for the ad creatives the engine diagnoses.
const STREAM_IMAGES = [
  { src: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1483985988355-763728e1935b?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?q=80&w=640&auto=format&fit=crop' },
  { src: 'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?q=80&w=640&auto=format&fit=crop' },
]

export default function StreamHero() {
  return (
    <section className="relative min-h-screen bg-noir pt-16" aria-label="Hero">
      {/* Silver-halide treatment for the corridor's imagery */}
      <style>{`
        .f1x8-stream img {
          filter: grayscale(0.85) contrast(1.08) brightness(0.8);
        }
      `}</style>

      {/* Film-grain overlay (matches the rest of the landing chrome) */}
      <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden="true">
        <filter id="stream-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </svg>

      <ImageStreamHero
        images={STREAM_IMAGES}
        speed={22}
        axis={55}
        className="f1x8-stream absolute inset-0"
      >
        {/* ── Atmosphere between corridor and copy ─────────────── */}
        <div className="absolute inset-0 bg-grid pointer-events-none" aria-hidden="true" />
        <div
          className="absolute inset-0 pointer-events-none"
          aria-hidden="true"
          style={{
            background:
              'radial-gradient(ellipse 52% 42% at 50% 55%, rgba(10,10,10,0.92), rgba(10,10,10,0.45) 58%, transparent 78%)',
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-noir to-transparent pointer-events-none"
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 pointer-events-none opacity-[0.12]"
          style={{ filter: 'url(#stream-grain)' }}
          aria-hidden="true"
        />

        {/* ── Interface overlay ────────────────────────────────── */}
        <div className="absolute inset-0 z-10 p-8 pt-24 md:p-14 md:pt-28 grid grid-cols-2 grid-rows-[auto_1fr_auto] pointer-events-none">

          {/* Status eyebrow */}
          <div className="flex items-start">
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full border border-white/10 bg-noir/60 backdrop-blur-sm animate-rise">
              <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" aria-hidden="true" />
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/55">
                Diagnostic engine · online
              </span>
            </div>
          </div>

          {/* Telemetry readout */}
          <div
            className="hidden sm:block text-right font-mono text-[10px] uppercase tracking-[0.18em] text-accent leading-relaxed animate-rise"
            style={{ animationDelay: '0.1s' }}
          >
            <div>Gaze sessions: 200,000+</div>
            <div>Benchmark: 30,000 ads</div>
            <div>Reading path: LTR / RTL</div>
          </div>

          {/* Headline */}
          <h1
            className="col-span-2 self-center text-center font-mono font-bold text-[#fafafa] tracking-tightest animate-rise"
            style={{
              fontSize: 'clamp(3rem, 9.5vw, 8.5rem)',
              lineHeight: 0.9,
              animationDelay: '0.16s',
            }}
          >
            See what
            <br />
            they <span className="text-white/40">see.</span>
          </h1>

          {/* Bottom row */}
          <div
            className="col-span-2 flex items-end justify-between gap-6 animate-rise"
            style={{ animationDelay: '0.24s' }}
          >
            <div className="font-mono text-[10px] md:text-[11px] uppercase tracking-[0.18em] text-white/45 leading-loose">
              <p>[ Cognitive diagnostics ]</p>
              <p className="hidden sm:block">Every frame below has been through the engine</p>
            </div>
            <div className="flex flex-col items-end gap-4 pointer-events-auto">
              <Link
                href="/upload"
                className="group inline-flex items-center gap-3 bg-accent text-[#0a0a0a] font-mono text-[11px]
                           font-medium uppercase tracking-[0.18em] px-8 py-4 rounded-[3px]
                           hover:bg-white transition-colors duration-300 ease-cinematic
                           shadow-[0_0_40px_-8px_rgba(224,224,224,0.35)]"
              >
                Run a diagnostic
                <ArrowRight />
              </Link>
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/35">
                No account required · Results in &lt; 30s
              </span>
            </div>
          </div>
        </div>
      </ImageStreamHero>

      {/* Scroll hint */}
      <div
        className="stream-scroll-hint absolute bottom-8 left-1/2 w-px h-14 bg-gradient-to-b from-white/40 to-transparent"
        aria-hidden="true"
      />
      <style>{`
        @keyframes stream-flow {
          0%, 100% { transform: scaleY(0); transform-origin: top; }
          50%      { transform: scaleY(1); transform-origin: top; }
          51%      { transform: scaleY(1); transform-origin: bottom; }
        }
        .stream-scroll-hint { animation: stream-flow 2s infinite ease-in-out; }
        @media (prefers-reduced-motion: reduce) {
          .stream-scroll-hint { animation: none; }
        }
      `}</style>
    </section>
  )
}

function ArrowRight() {
  return (
    <svg width="16" height="12" viewBox="0 0 16 12" fill="none" aria-hidden="true"
      className="transition-transform duration-300 ease-cinematic group-hover:translate-x-1">
      <path d="M1 6h13M10 1l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
