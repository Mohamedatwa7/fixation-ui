'use client'
import { useState } from 'react'
import type { DiagnosticResult } from '@/lib/mock-data'
import { scoreColor, SCORE_MID } from '@/lib/score'

interface Props {
  result: DiagnosticResult
}

export default function FullDiagnostic({ result }: Props) {
  const [open, setOpen] = useState(false)
  const [jsonOpen, setJsonOpen] = useState(false)

  return (
    <div className="border border-white/10 rounded-[2px] overflow-hidden">
      {/* Toggle header */}
      <button
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-7 py-5 bg-[#141312] hover:bg-[#1a1816] transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/55">
          Full Diagnostic
        </span>
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div className="border-t border-white/10">

          {/* Attention Heatmap */}
          <div className="border-b border-white/10 p-7">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-4">
              Attention Heatmap
            </p>
            {result.heatmapDataUrl ? (
              <div className="relative bg-black border border-white/10 rounded-[2px] overflow-hidden">
                {result.mediaType === 'video' ? (
                  <video
                    src={result.heatmapDataUrl}
                    controls
                    className="w-full max-h-[480px] object-contain"
                    aria-label="Attention heatmap video"
                  />
                ) : (
                  <img
                    src={result.heatmapDataUrl}
                    alt="Attention heatmap"
                    className="w-full max-h-[480px] object-contain"
                  />
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-32 border border-dashed border-white/10 rounded-[2px] bg-black/40">
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/30">
                  Heatmap not available for this result
                </span>
              </div>
            )}
          </div>

          {/* Full KPI breakdown */}
          <div className="border-b border-white/10 p-7">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-5">
              KPI Breakdown
            </p>
            <div className="space-y-6">
              {result.kpis.map(kpi => (
                <KpiRow key={kpi.id} kpi={kpi} />
              ))}
            </div>
          </div>

          {/* Strengths + Risks */}
          <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-white/10 border-b border-white/10">
            <div className="p-7">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-4">
                Strengths
              </p>
              <ul className="space-y-3">
                {result.strengths.map((s, i) => (
                  <li key={i} className="flex gap-3 prose-serif text-base text-white/65">
                    <span className="text-accent mt-px flex-shrink-0">+</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="p-7">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-4">
                Risks
              </p>
              <ul className="space-y-3">
                {result.risks.map((r, i) => (
                  <li key={i} className="flex gap-3 prose-serif text-base text-white/65">
                    <span className="mt-px flex-shrink-0" style={{ color: SCORE_MID }}>!</span>
                    <span>
                      {r.issue}
                      {r.impact && <span className="text-white/40"> — {r.impact}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Raw JSON */}
          <div className="p-7 bg-[#0b0b0a]">
            <button
              onClick={() => setJsonOpen(v => !v)}
              aria-expanded={jsonOpen}
              className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 hover:text-accent transition-colors duration-300 mb-3 focus:outline-none"
            >
              <ChevronIcon open={jsonOpen} size={10} />
              Raw JSON
            </button>
            {jsonOpen && (
              <pre className="font-mono text-[10px] text-white/45 leading-relaxed overflow-x-auto border border-white/10 rounded-[2px] p-4 bg-black max-h-80">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── KPI row with score bar ─────────────────────────────────────────────────── */
function KpiRow({ kpi }: { kpi: import('@/lib/mock-data').KPI }) {
  const color = scoreColor(kpi.score)

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="prose-serif text-lg text-paper">{kpi.label}</span>
        <span className="font-mono text-sm font-medium" style={{ color }}>
          {kpi.score.toFixed(1)}
        </span>
      </div>
      {/* Score bar */}
      <div className="h-px bg-white/10 mb-2.5 overflow-hidden">
        <div
          className="h-full transition-all duration-700 ease-cinematic"
          style={{ width: `${kpi.score * 10}%`, backgroundColor: color }}
          role="meter"
          aria-valuenow={kpi.score}
          aria-valuemin={0}
          aria-valuemax={10}
          aria-label={kpi.label}
        />
      </div>
      <p className="prose-serif text-[0.95rem] text-white/55 mb-1.5">
        {kpi.methodology}
      </p>
      <p className="font-mono text-[10px] text-white/35">{kpi.citation}</p>
    </div>
  )
}

/* ── Chevron icon ────────────────────────────────────────────────────────────── */
function ChevronIcon({ open, size = 12 }: { open: boolean; size?: number }) {
  return (
    <svg
      width={size} height={size}
      viewBox="0 0 12 12" fill="none" aria-hidden="true"
      className={`transition-transform duration-300 text-white/40 ${open ? 'rotate-180' : ''}`}
    >
      <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
