'use client'

import { useEffect, useRef, useState } from 'react'
import type { DiagnosticResult } from '@/lib/mock-data'
import { scoreColor } from '@/lib/score'

// Engagement Potential band — same 0–10 thresholds as the score colour scale.
function engagementBand(score: number): string {
  if (score >= 7) return 'STRONG'
  if (score >= 4) return 'MODERATE'
  return 'WEAK'
}

const FUNNEL_LABEL: Record<string, string> = {
  upper: 'AWARENESS',
  mid: 'CONSIDERATION',
  lower: 'CONVERSION',
}

type Layer = 'creative' | 'attention'

/**
 * The results-page signature: the analyzed creative presented as a tilted
 * specimen plate (same 3D language as the landing hero), toggling between the
 * creative itself and its real attention heatmap, with the verdict readout
 * beside it. Score counts up on entry; a scan line sweeps the plate once.
 */
export default function SpecimenVerdict({ result }: { result: DiagnosticResult }) {
  const score = result.score ?? 0
  const color = scoreColor(score)
  const isVideoHeatmap = result.heatmapDataUrl?.startsWith('data:video')

  const hasCreative = Boolean(result.sourcePreview)
  const hasAttention = Boolean(result.heatmapDataUrl)
  const [layer, setLayer] = useState<Layer>(hasAttention ? 'attention' : 'creative')

  const plateRef = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(0)

  // Count-up score (respects reduced motion)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setShown(score)
      return
    }
    const t0 = performance.now()
    const dur = 900
    let raf = 0
    const tick = (t: number) => {
      const p = Math.min((t - t0) / dur, 1)
      setShown(score * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [score])

  // Subtle mouse parallax on the plate
  useEffect(() => {
    const plate = plateRef.current
    if (!plate || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const onMove = (e: MouseEvent) => {
      const x = (window.innerWidth / 2 - e.clientX) / 90
      const y = (window.innerHeight / 2 - e.clientY) / 90
      plate.style.transform = `rotateX(${10 + y / 2}deg) rotateZ(${-4 + x / 3}deg)`
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  const img = layer === 'attention' ? result.heatmapDataUrl : result.sourcePreview
  const showToggle = hasCreative && hasAttention

  return (
    <div className="relative border border-white/10 bg-panel rounded-[3px] overflow-hidden">
      <style>{`
        @keyframes specimen-scan {
          0% { top: -8%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 104%; opacity: 0; }
        }
        .specimen-scanline { animation: specimen-scan 1.6s cubic-bezier(0.4, 0, 0.2, 1) 0.4s 1 both; }
        @media (prefers-reduced-motion: reduce) {
          .specimen-scanline { animation: none; opacity: 0; }
        }
      `}</style>
      <div className="absolute inset-0 bg-grid pointer-events-none" aria-hidden="true" />

      <div className="relative grid grid-cols-1 lg:grid-cols-[5fr_6fr]">

        {/* ── Specimen plate ─────────────────────────────── */}
        <div className="relative flex items-center justify-center p-8 md:p-10 min-h-[300px] lg:min-h-[380px] lg:border-r border-b lg:border-b-0 border-white/10">
          <div style={{ perspective: '1600px' }}>
            <div
              ref={plateRef}
              className="relative transition-transform duration-500 ease-out"
              style={{ transform: 'rotateX(10deg) rotateZ(-4deg)', transformStyle: 'preserve-3d' }}
            >
              <div className="relative border border-white/15 rounded-[2px] bg-noir overflow-hidden max-w-[340px]">
                {img ? (
                  isVideoHeatmap && layer === 'attention' ? (
                    <video src={img} autoPlay loop muted playsInline
                      className="block max-h-[300px] lg:max-h-[360px] w-auto"
                      aria-label="Attention heatmap video" />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={img} alt={layer === 'attention' ? 'Attention heatmap of your creative' : 'Your creative'}
                      className="block max-h-[300px] lg:max-h-[360px] w-auto" />
                  )
                ) : (
                  // No imagery available (mock/session-restored result) — wireframe placeholder
                  <div className="w-[280px] h-[300px] relative bg-panel" aria-label="Creative preview unavailable">
                    <div className="absolute left-[8%] top-[10%] w-[55%] h-[55%] border border-white/15 bg-white/[0.04]" />
                    <div className="absolute right-[8%] top-[16%] w-[26%] h-1.5 bg-white/20" />
                    <div className="absolute right-[8%] top-[26%] w-[20%] h-1.5 bg-white/10" />
                    <div className="absolute right-[8%] bottom-[16%] w-[22%] h-6 border border-white/30 rounded-[2px]" />
                    <span className="absolute left-[8%] bottom-[5%] font-mono text-[9px] uppercase tracking-[0.2em] text-white/30">
                      Preview unavailable
                    </span>
                  </div>
                )}
                {/* one-time scan sweep */}
                <div className="specimen-scanline absolute left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-white/70 to-transparent pointer-events-none" aria-hidden="true" />
              </div>
              {/* corner ticks */}
              <div aria-hidden="true" className="pointer-events-none absolute -inset-2.5">
                <span className="absolute top-0 left-0 w-3.5 h-3.5 border-t border-l border-white/30" />
                <span className="absolute top-0 right-0 w-3.5 h-3.5 border-t border-r border-white/30" />
                <span className="absolute bottom-0 left-0 w-3.5 h-3.5 border-b border-l border-white/30" />
                <span className="absolute bottom-0 right-0 w-3.5 h-3.5 border-b border-r border-white/30" />
              </div>
            </div>
          </div>

          {/* layer toggle */}
          {showToggle && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex rounded-[3px] overflow-hidden border border-white/15 bg-noir/80 backdrop-blur-sm">
              {(['creative', 'attention'] as Layer[]).map(l => (
                <button
                  key={l}
                  onClick={() => setLayer(l)}
                  aria-pressed={layer === l}
                  className={`px-4 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors duration-300
                    ${layer === l ? 'bg-accent text-[#0a0a0a]' : 'text-white/45 hover:text-white/80'}`}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
          {!showToggle && hasAttention && (
            <span className="absolute bottom-4 left-1/2 -translate-x-1/2 font-mono text-[9px] uppercase tracking-[0.2em] text-white/35">
              Attention map
            </span>
          )}
        </div>

        {/* ── Verdict readout ────────────────────────────── */}
        <div className="relative p-7 md:p-10 flex flex-col justify-center">
          <span
            className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40"
            title={result.organicSource === 'ranker'
              ? 'Fine-tuned ranker calibrated on realized organic engagement — picks the better performer of a pair ~85 times out of 100 on held-out creatives'
              : undefined}
          >
            {result.scoreLabel ?? 'Engagement Potential'}
          </span>
          <div className="flex items-end gap-4 mt-2">
            <span
              className="font-mono font-semibold leading-[0.85] tracking-tightest tabular-nums"
              style={{ fontSize: 'clamp(4rem, 8vw, 6.5rem)', color }}
              aria-label={`${result.scoreLabel ?? 'Engagement Potential'}: ${score} out of 10`}
            >
              {shown.toFixed(1)}
            </span>
            <div className="flex flex-col gap-1.5 pb-1.5">
              <span
                className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] px-2.5 py-1 rounded-[2px] border w-fit"
                style={{ color, borderColor: `${color}55`, backgroundColor: `${color}12` }}
              >
                {engagementBand(score)}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/35">
                out of 10
              </span>
            </div>
          </div>

          <p className="font-sans text-lg md:text-xl font-medium text-[#fafafa] leading-snug mt-6 mb-6 tracking-tight">
            {result.verdict}
          </p>

          <div className="flex flex-wrap items-center gap-2.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/55 border border-white/10 px-2.5 py-1 rounded-[2px]">
              {result.role}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/55 border border-white/10 px-2.5 py-1 rounded-[2px]">
              {result.format}
            </span>
            {result.funnelStage && (
              <span
                className="font-mono text-[10px] uppercase tracking-[0.16em] text-accent/80 border border-accent/25 bg-accent/5 px-2.5 py-1 rounded-[2px]"
                title={result.productTier ? `Scored as ${result.productTier} tier` : undefined}
              >
                {FUNNEL_LABEL[result.funnelStage] ?? result.funnelStage}
              </span>
            )}
            {typeof result.craftScore === 'number' ? (
              <span
                className="font-mono text-[10px] uppercase tracking-[0.16em] px-2.5 py-1 rounded-[2px] border"
                style={{
                  color: scoreColor(result.craftScore),
                  borderColor: `${scoreColor(result.craftScore)}40`,
                }}
                title="Craft: funnel-weighted execution quality — how well the creative is built for its funnel job, independent of in-feed pull"
              >
                Craft {result.craftScore.toFixed(1)}
              </span>
            ) : typeof result.organicEngagement === 'number' && (
              <span
                className="font-mono text-[10px] uppercase tracking-[0.16em] px-2.5 py-1 rounded-[2px] border"
                style={{
                  color: scoreColor(result.organicEngagement),
                  borderColor: `${scoreColor(result.organicEngagement)}40`,
                }}
                title="Organic pull (beta): KPI weighting calibrated against realized organic social engagement — reads in-feed appeal, not paid-media craft"
              >
                Organic {result.organicEngagement.toFixed(1)}
              </span>
            )}
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/35 pl-1">
              Better than <span className="text-accent">{result.benchmarkPercentile}%</span> of category
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
