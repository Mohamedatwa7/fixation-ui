'use client'

import Link from 'next/link'
import { useEffect, useRef } from 'react'
const SILVER = '#e0e0e0'
const SILVER_DIM = '#8f8c85'

/**
 * 3D parallax hero — a tilted "specimen plate" showing what F1X8 does:
 * a wireframed ad creative, its saliency heatmap, and the predicted
 * fixation scanpath, stacked in Z and shifting with the cursor.
 */
export default function ParallaxHero() {
  const canvasRef = useRef<HTMLDivElement>(null)
  const layersRef = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (reducedMotion) {
      canvas.style.opacity = '1'
      canvas.style.transform = 'rotateX(55deg) rotateZ(-25deg)'
      return
    }

    const handleMouseMove = (e: MouseEvent) => {
      const x = (window.innerWidth / 2 - e.clientX) / 25
      const y = (window.innerHeight / 2 - e.clientY) / 25

      canvas.style.transform = `rotateX(${55 + y / 2}deg) rotateZ(${-25 + x / 2}deg)`

      layersRef.current.forEach((layer, index) => {
        if (!layer) return
        const depth = (index + 1) * 28
        const moveX = x * (index + 1) * 0.2
        const moveY = y * (index + 1) * 0.2
        layer.style.transform = `translateZ(${depth}px) translate(${moveX}px, ${moveY}px)`
      })
    }

    canvas.style.opacity = '0'
    canvas.style.transform = 'rotateX(90deg) rotateZ(0deg) scale(0.85)'

    const entrance = setTimeout(() => {
      canvas.style.transition = 'all 2.2s cubic-bezier(0.16, 1, 0.3, 1)'
      canvas.style.opacity = '1'
      canvas.style.transform = 'rotateX(55deg) rotateZ(-25deg) scale(1)'
    }, 300)

    // Hand transform control back to the (faster) CSS transition once the
    // entrance settles, otherwise parallax drags at 2.2s.
    const settle = setTimeout(() => {
      canvas.style.transition = ''
      window.addEventListener('mousemove', handleMouseMove)
    }, 2600)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      clearTimeout(entrance)
      clearTimeout(settle)
    }
  }, [])

  return (
    <section
      className="relative min-h-screen overflow-hidden bg-noir pt-16"
      aria-label="Hero"
    >
      <style>{`
        .hero3d-viewport {
          perspective: 2000px;
        }
        .hero3d-canvas {
          position: relative;
          width: min(820px, 92vw);
          aspect-ratio: 8 / 5;
          transform-style: preserve-3d;
          transform: rotateX(55deg) rotateZ(-25deg);
          transition: transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .hero3d-layer {
          position: absolute;
          inset: 0;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 3px;
          transition: transform 0.5s ease;
        }
        .hero3d-heatmap {
          background:
            radial-gradient(circle at 30% 36%, rgba(255, 255, 255, 0.50) 0%, transparent 32%),
            radial-gradient(circle at 63% 58%, rgba(224, 224, 224, 0.32) 0%, transparent 30%),
            radial-gradient(circle at 76% 24%, rgba(160, 158, 152, 0.25) 0%, transparent 24%);
          filter: blur(14px);
          mix-blend-mode: screen;
          border: none;
        }
        .hero3d-contours {
          position: absolute;
          width: 200%;
          height: 200%;
          top: -50%;
          left: -50%;
          background-image: repeating-radial-gradient(
            circle at 38% 42%,
            transparent 0,
            transparent 40px,
            rgba(232, 227, 214, 0.05) 41px,
            transparent 42px
          );
          transform: translateZ(112px);
          pointer-events: none;
        }
        @keyframes hero3d-flow {
          0%, 100% { transform: scaleY(0); transform-origin: top; }
          50%      { transform: scaleY(1); transform-origin: top; }
          51%      { transform: scaleY(1); transform-origin: bottom; }
        }
        .hero3d-scroll-hint {
          animation: hero3d-flow 2s infinite ease-in-out;
        }
        @media (prefers-reduced-motion: reduce) {
          .hero3d-scroll-hint { animation: none; }
        }
      `}</style>

      {/* Film-grain overlay */}
      <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden="true">
        <filter id="hero3d-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </svg>
      <div
        className="absolute inset-0 z-30 pointer-events-none opacity-[0.12]"
        style={{ filter: 'url(#hero3d-grain)' }}
        aria-hidden="true"
      />

      {/* Backdrops */}
      <div className="absolute inset-0 bg-grid" aria-hidden="true" />
      <div className="absolute inset-0 spotlight" aria-hidden="true" />

      {/* ── 3D specimen plate ─────────────────────────────────── */}
      <div className="hero3d-viewport absolute inset-0 flex items-center justify-center overflow-hidden">
        <div className="hero3d-canvas" ref={canvasRef} style={{ opacity: 0 }} aria-hidden="true">

          {/* Layer I — the creative (wireframe specimen) */}
          <div
            className="hero3d-layer bg-panel"
            ref={el => { layersRef.current[0] = el }}
          >
            <div className="absolute inset-0 bg-grid opacity-60" />
            {/* image block */}
            <div className="absolute left-[6%] top-[10%] w-[52%] h-[62%] border border-white/15 bg-gradient-to-br from-white/[0.06] to-transparent" />
            {/* headline bars */}
            <div className="absolute right-[6%] top-[16%] w-[30%] h-2 bg-white/20" />
            <div className="absolute right-[6%] top-[24%] w-[24%] h-2 bg-white/10" />
            <div className="absolute right-[6%] top-[32%] w-[27%] h-2 bg-white/10" />
            {/* CTA chip */}
            <div className="absolute right-[6%] bottom-[14%] w-[18%] h-8 border border-accent/70 rounded-[2px]" />
            <span className="absolute left-[6%] bottom-[4%] font-mono text-[9px] uppercase tracking-[0.22em] text-white/30">
              Specimen 001 — Static · 4:5
            </span>
          </div>

          {/* Layer II — saliency heatmap */}
          <div
            className="hero3d-layer hero3d-heatmap"
            ref={el => { layersRef.current[1] = el }}
          />

          {/* Layer III — fixation scanpath */}
          <div
            className="hero3d-layer"
            ref={el => { layersRef.current[2] = el }}
            style={{ border: 'none' }}
          >
            <svg viewBox="0 0 800 500" className="w-full h-full" fill="none">
              <polyline
                points="240,180 504,290 608,120 336,392"
                stroke={SILVER}
                strokeOpacity="0.45"
                strokeWidth="1"
                strokeDasharray="5 5"
              />
              {[
                { x: 240, y: 180, n: 'I', c: '#ffffff' },
                { x: 504, y: 290, n: 'II', c: SILVER },
                { x: 608, y: 120, n: 'III', c: SILVER },
                { x: 336, y: 392, n: 'IV', c: SILVER_DIM },
              ].map(p => (
                <g key={p.n}>
                  <circle cx={p.x} cy={p.y} r="16" stroke={p.c} strokeOpacity="0.9" strokeWidth="1" />
                  <circle cx={p.x} cy={p.y} r="3" fill={p.c} />
                  <text
                    x={p.x + 24}
                    y={p.y + 4}
                    fill={p.c}
                    fontSize="13"
                    fontFamily="var(--font-geist-mono), monospace"
                    letterSpacing="0.15em"
                  >
                    {p.n}
                  </text>
                </g>
              ))}
            </svg>
          </div>

          {/* Topographic contour field */}
          <div className="hero3d-contours" />
        </div>
      </div>

      {/* ── Interface overlay ─────────────────────────────────── */}
      <div className="absolute inset-0 z-20 p-8 pt-24 md:p-14 md:pt-28 grid grid-cols-2 grid-rows-[auto_1fr_auto] pointer-events-none">

        {/* Status eyebrow */}
        <div className="flex items-start">
          <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full border border-white/10 bg-noir/60 animate-rise">
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
          className="col-span-2 self-center font-mono font-bold text-[#fafafa] tracking-tightest mix-blend-difference animate-rise"
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
            <p className="hidden sm:block">Attention, mapped before launch</p>
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

      {/* Scroll hint */}
      <div
        className="hero3d-scroll-hint absolute bottom-8 left-1/2 w-px h-14 bg-gradient-to-b from-white/40 to-transparent"
        aria-hidden="true"
      />
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
