import type { DiagnosticResult } from '@/lib/mock-data'
import { scoreColor, scoreLabel } from '@/lib/score'

interface Props {
  result: DiagnosticResult
}

export default function VerdictBlock({ result }: Props) {
  const score = result.score ?? 0
  const color = scoreColor(score)

  return (
    <div className="border border-white/10 bg-panel rounded-[3px] p-7 md:p-10">
      <div className="flex flex-col sm:flex-row sm:items-start gap-7 md:gap-12">

        {/* Score column */}
        <div className="flex-shrink-0 flex flex-col items-start gap-3">
          <span
            className="font-mono font-semibold leading-[0.85] tracking-tightest"
            style={{ fontSize: 'clamp(4rem, 9vw, 6.5rem)', color }}
            aria-label={`Score: ${score} out of 10`}
          >
            {score.toFixed(1)}
          </span>
          <div className="flex items-center gap-2.5">
            <span
              className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] px-2.5 py-1 rounded-[2px] border"
              style={{ color, borderColor: `${color}55`, backgroundColor: `${color}12` }}
            >
              {scoreLabel(score)}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/35">
              out of 10
            </span>
          </div>
        </div>

        {/* Verdict + meta */}
        <div className="flex-1 sm:pt-1">
          <p className="font-sans text-xl md:text-2xl font-medium text-[#fafafa] leading-snug mb-6 tracking-tight">
            {result.verdict}
          </p>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Role pill */}
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/55 border border-white/10 px-2.5 py-1 rounded-[2px]">
              {result.role}
            </span>

            {/* Format pill */}
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/55 border border-white/10 px-2.5 py-1 rounded-[2px]">
              {result.format}
            </span>

            {/* Benchmark */}
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/35 pl-1">
              Better than{' '}
              <span className="text-accent">{result.benchmarkPercentile}%</span>
              {' '}of category
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
