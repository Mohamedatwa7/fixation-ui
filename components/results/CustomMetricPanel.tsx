'use client'
import { useState } from 'react'
import { askQuestion } from '@/lib/api'
import type { AskVerdict } from '@/lib/api'
import { SCORE_HIGH, SCORE_MID, SCORE_LOW } from '@/lib/score'

interface Props {
  diagnosticId: string
}

const AI_GOLD = SCORE_MID // AI-judgment accent — distinct from grounded KPIs

const CONFIDENCE_COLOR: Record<AskVerdict['confidence'], string> = {
  high: SCORE_HIGH,
  medium: SCORE_MID,
  low: SCORE_LOW,
}

const VERDICT_LABEL: Record<AskVerdict['verdict'], string> = {
  works: 'Works',
  works_with_conditions: 'Works with conditions',
  unlikely: 'Unlikely',
}

const VERDICT_COLOR: Record<AskVerdict['verdict'], string> = {
  works: SCORE_HIGH,
  works_with_conditions: SCORE_MID,
  unlikely: SCORE_LOW,
}

const SUGGESTIONS = [
  'Would this work for 30–40 year old women with above-average income?',
  'Would this hold its own against a major competitor launch this quarter?',
  'Is this strong enough to lead a paid social push?',
  'Would Gen-Z engage with this organically?',
]

export default function CustomMetricPanel({ diagnosticId: _diagnosticId }: Props) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<AskVerdict | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || isLoading) return
    setIsLoading(true)
    setResult(null)
    setError(null)
    try {
      setResult(await askQuestion(query.trim()))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="border border-white/10 bg-panel rounded-[3px] p-7">
      <div className="mb-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-2">
          Ask a business question
        </p>
        <p className="font-sans text-sm text-white/55 max-w-lg leading-relaxed">
          Would this creative work for your audience, moment, or channel? Answered
          against this diagnostic&apos;s measured evidence plus a simulated audience
          read — returned as AI judgment, clearly distinguished from grounded
          measurements.
        </p>
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2.5 mb-4">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. would this work for 30–40 year old women?"
          className="flex-1 bg-noir border border-white/10 rounded-[3px] px-4 py-3 font-mono text-xs text-[#fafafa] placeholder-white/30 focus:outline-none focus:border-accent transition-colors duration-300"
          aria-label="Business question"
        />
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          className="px-5 py-3 bg-[#fafafa] text-[#0a0a0a] text-[10px] font-mono uppercase tracking-[0.16em] rounded-[3px]
                     hover:bg-accent hover:text-[#0a0a0a] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-[#fafafa] disabled:hover:text-[#0a0a0a]
                     transition-colors duration-300 whitespace-nowrap"
        >
          {isLoading ? (
            <span className="flex items-center gap-1.5">
              <SpinnerIcon />
              Analyzing
            </span>
          ) : 'Ask'}
        </button>
      </form>

      {/* Suggestions */}
      <div className="flex flex-wrap gap-2 mb-6">
        {SUGGESTIONS.map(s => (
          <button
            key={s}
            type="button"
            onClick={() => setQuery(s)}
            className="font-mono text-[10px] tracking-[0.04em] text-white/40 border border-white/10 rounded-[3px] px-2.5 py-1.5 text-left
                       hover:border-accent hover:text-accent transition-colors duration-300"
          >
            {s}
          </button>
        ))}
      </div>

      {isLoading && (
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/35">
          Running audience panel + grounded synthesis — typically 30–60s…
        </p>
      )}

      {error && (
        <p className="font-sans text-sm" style={{ color: SCORE_LOW }}>{error}</p>
      )}

      {/* Verdict card */}
      {result && (
        <div
          className="border rounded-[3px] p-5"
          style={{ borderColor: `${AI_GOLD}33`, backgroundColor: `${AI_GOLD}0d` }}
        >
          {/* AI Judgment badge — visually distinct from grounded KPIs */}
          <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
            <div className="flex items-center gap-2.5">
              <span
                className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] px-2.5 py-1 rounded-[3px] border"
                style={{ color: AI_GOLD, backgroundColor: `${AI_GOLD}1f`, borderColor: `${AI_GOLD}40` }}
              >
                ⚠ AI Judgment
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/40">
                not a grounded measurement
              </span>
            </div>
            <span
              className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] px-2.5 py-1 rounded-[3px]"
              style={{
                color: CONFIDENCE_COLOR[result.confidence],
                backgroundColor: `${CONFIDENCE_COLOR[result.confidence]}15`,
                border: `1px solid ${CONFIDENCE_COLOR[result.confidence]}30`,
              }}
            >
              {result.confidence} confidence
            </span>
          </div>

          <div className="flex items-baseline gap-4 mb-3 flex-wrap">
            <span
              className="font-mono font-semibold text-4xl leading-none tracking-tightest"
              style={{ color: VERDICT_COLOR[result.verdict] }}
            >
              {result.score.toFixed(1)}
            </span>
            <span
              className="font-sans text-base font-medium"
              style={{ color: VERDICT_COLOR[result.verdict] }}
            >
              {VERDICT_LABEL[result.verdict]}
            </span>
            {result.used_web_search && (
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/35">
                incl. live market research
              </span>
            )}
          </div>

          <p className="font-sans text-sm text-white/60 leading-relaxed mb-5">
            {result.reasoning}
          </p>

          {/* Simulated audience read */}
          {result.audience_read && result.audience_read.length > 0 && (
            <div className="mb-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2.5">
                Simulated audience read
              </p>
              <div className="grid gap-2.5 sm:grid-cols-3">
                {result.audience_read.map((p, i) => (
                  <div key={i} className="border border-white/10 bg-noir/60 rounded-[3px] p-3.5">
                    <div className="flex items-baseline justify-between mb-1.5">
                      <span className="font-mono font-semibold text-lg" style={{ color: AI_GOLD }}>
                        {p.appeal_score.toFixed(0)}/10
                      </span>
                      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-white/35">
                        {p.would_stop_scrolling ? 'stops scroll' : 'scrolls past'}
                      </span>
                    </div>
                    <p className="font-sans text-xs text-white/45 leading-snug mb-2">
                      {p.persona.replace(/^You are\s*/i, '')}
                    </p>
                    <p className="font-sans text-xs text-white/60 italic leading-snug">
                      “{p.reaction}”
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* What would make it work */}
          {result.what_would_make_it_work?.length > 0 && (
            <div className="mb-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">
                What would make it work
              </p>
              <ul className="space-y-1.5">
                {result.what_would_make_it_work.map((s, i) => (
                  <li key={i} className="font-sans text-sm text-white/60 leading-snug pl-4 relative">
                    <span className="absolute left-0 text-accent">→</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Watchouts */}
          {result.watchouts?.length > 0 && (
            <div className="mb-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">
                Watchouts
              </p>
              <ul className="space-y-1.5">
                {result.watchouts.map((s, i) => (
                  <li key={i} className="font-sans text-xs text-white/45 leading-snug pl-4 relative">
                    <span className="absolute left-0" style={{ color: SCORE_LOW }}>!</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Evidence trail */}
          {result.evidence_used?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {result.evidence_used.map((tag, i) => (
                <span
                  key={i}
                  className="font-mono text-[9px] uppercase tracking-[0.1em] text-white/35 border border-white/10 rounded-[3px] px-2 py-0.5"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SpinnerIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="animate-spin">
      <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
        strokeDasharray="22" strokeDashoffset="8" />
    </svg>
  )
}
