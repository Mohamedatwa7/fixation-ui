import type { KPI } from '@/lib/mock-data'
import { scoreColor } from '@/lib/score'

interface Props {
  kpis: KPI[]
}

export default function KpiStrip({ kpis }: Props) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-4">
        Diagnostics
      </p>
      <div className="grid grid-cols-3 md:grid-cols-6 border border-white/10 rounded-[2px] overflow-hidden">
        {kpis.map((kpi, i) => (
          <div
            key={kpi.id}
            className={`relative group bg-[#141312] px-4 py-6 flex flex-col gap-2.5
              hover:bg-[#1a1816] transition-colors duration-300
              ${i > 0 ? 'border-l border-white/10' : ''}
              ${i >= 3 ? 'border-t border-white/10 md:border-t-0' : ''}
            `}
          >
            <span
              className="font-mono font-medium text-[1.75rem] leading-none"
              style={{ color: scoreColor(kpi.score) }}
              aria-label={`${kpi.label}: ${kpi.score}`}
            >
              {kpi.score.toFixed(1)}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/45 leading-tight">
              {kpi.shortLabel}
            </span>

            {/* Citation tooltip — CSS only, no JS */}
            <div
              role="tooltip"
              className="
                absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56
                bg-[#1a1816] border border-white/15 rounded-[2px]
                px-3 py-3 z-20 pointer-events-none
                opacity-0 group-hover:opacity-100
                transition-opacity duration-300
                shadow-xl
              "
            >
              <p className="prose-serif text-sm text-paper mb-1.5">{kpi.label}</p>
              <p className="font-mono text-[10px] text-white/45 leading-relaxed">{kpi.citation}</p>
            </div>
          </div>
        ))}
      </div>
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/30 mt-3">
        Hover each metric for its research citation.
      </p>
    </div>
  )
}
