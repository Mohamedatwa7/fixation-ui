import type { KPI } from '@/lib/mock-data'
import { scoreColor } from '@/lib/score'

interface Props {
  kpis: KPI[]
}

// Index markers — KPIs arrive in funnel-weight order from the backend, so the
// numeral encodes "how much this dimension drives the verdict for this asset".
const NUMERAL = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII']

export default function KpiStrip({ kpis }: Props) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40">
          Diagnostics
        </p>
        <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-white/25">
          Ordered by weight in this verdict
        </p>
      </div>
      <div
        className="grid border border-white/10 rounded-[3px] overflow-hidden bg-noir gap-px"
        style={{ gridTemplateColumns: `repeat(auto-fit, minmax(150px, 1fr))` }}
      >
        {kpis.map((kpi, i) => {
          const color = scoreColor(kpi.score)
          return (
            <div
              key={kpi.id}
              className="relative group bg-panel px-4 py-6 flex flex-col gap-2.5 hover:bg-elevated transition-colors duration-300"
            >
              <span className="font-mono text-[10px] tracking-[0.2em] text-white/30">
                {NUMERAL[i] ?? i + 1}
              </span>
              <span
                className="font-mono font-medium text-[1.75rem] leading-none tabular-nums"
                style={{ color }}
                aria-label={`${kpi.label}: ${kpi.score}`}
              >
                {kpi.score.toFixed(1)}
              </span>
              {/* score bar — instrument readout, same color scale */}
              <div className="h-px w-full bg-white/10" aria-hidden="true">
                <div
                  className="h-px transition-all duration-700 ease-out"
                  style={{ width: `${Math.max(0, Math.min(10, kpi.score)) * 10}%`, backgroundColor: color }}
                />
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/45 leading-tight">
                {kpi.shortLabel}
              </span>

              {/* Citation tooltip — CSS only, no JS */}
              <div
                role="tooltip"
                className="
                  absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56
                  bg-elevated border border-white/15 rounded-[3px]
                  px-3 py-3 z-20 pointer-events-none
                  opacity-0 group-hover:opacity-100
                  transition-opacity duration-300
                  shadow-xl
                "
              >
                <p className="font-sans text-sm font-medium text-[#fafafa] mb-1.5">{kpi.label}</p>
                <p className="font-mono text-[10px] text-white/45 leading-relaxed">{kpi.citation}</p>
              </div>
            </div>
          )
        })}
      </div>
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/30 mt-3">
        Hover each metric for its research citation.
      </p>
    </div>
  )
}
