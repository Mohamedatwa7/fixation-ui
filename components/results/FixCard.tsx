import type { DiagnosticResult } from '@/lib/mock-data'

interface Props {
  fix: DiagnosticResult['fix']
}

export default function FixCard({ fix }: Props) {
  return (
    <div className="rounded-[2px] border border-white/10 overflow-hidden">
      <div className="flex">
        {/* Accent left rule */}
        <div className="w-[3px] flex-shrink-0 bg-accent" aria-hidden="true" />
        <div className="flex-1 bg-[#141312] px-7 py-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent mb-4">
            The Fix
          </p>
          <p className="prose-serif text-lg text-white/55 mb-5">
            {fix.issue}
          </p>
          <p className="prose-serif text-lg text-paper flex gap-3">
            <span className="text-accent flex-shrink-0">→</span>
            <span>{fix.action}</span>
          </p>
        </div>
      </div>
    </div>
  )
}
