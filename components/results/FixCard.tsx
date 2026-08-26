import type { DiagnosticResult } from '@/lib/mock-data'

interface Props {
  fix: DiagnosticResult['fix']
  revisionBrief?: DiagnosticResult['revisionBrief']
}

export default function FixCard({ fix, revisionBrief }: Props) {
  const hasBrief = !!revisionBrief?.sections?.length
  return (
    <div className="rounded-[2px] border border-white/10 overflow-hidden">
      <div className="flex">
        {/* Accent left rule */}
        <div className="w-[3px] flex-shrink-0 bg-accent" aria-hidden="true" />
        <div className="flex-1 bg-panel px-7 py-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent mb-4">
            The Fix
          </p>
          <p className="font-sans text-[15px] text-white/55 leading-relaxed mb-5">
            {fix.issue}
          </p>
          <p className="font-sans text-[15px] text-[#fafafa] leading-relaxed flex gap-3">
            <span className="font-mono text-accent flex-shrink-0">→</span>
            <span>{fix.action}</span>
          </p>

          {hasBrief && (
            <div className="mt-7 pt-6 border-t border-white/10">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent mb-1.5">
                Revision Brief
              </p>
              {revisionBrief!.objective && (
                <p className="font-sans text-[15px] font-medium text-[#fafafa] leading-relaxed mb-5">
                  {revisionBrief!.objective}
                </p>
              )}
              <div className="flex flex-col gap-4">
                {revisionBrief!.sections.map(section => (
                  <div key={section.title} className="grid grid-cols-1 sm:grid-cols-[130px_1fr] gap-1.5 sm:gap-4">
                    <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/45 pt-0.5">
                      {section.title}
                    </span>
                    <p className="font-sans text-[14px] text-white/70 leading-relaxed">
                      {section.detail}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
