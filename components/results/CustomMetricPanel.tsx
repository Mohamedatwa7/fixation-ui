'use client'
import { useState } from 'react'
import { getCustomMetric } from '@/lib/api'
import type { CustomMetricResult } from '@/lib/mock-data'
import { SCORE_HIGH, SCORE_MID, SCORE_LOW } from '@/lib/score'

interface Props {
  diagnosticId: string
}

const AI_GOLD = SCORE_MID // AI-judgment accent — distinct from grounded KPIs

const CONFIDENCE_LABEL: Record<CustomMetricResult['confidence'], string> = {
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
}

const CONFIDENCE_COLOR: Record<CustomMetricResult['confidence'], string> = {
  high: SCORE_HIGH,
  medium: SCORE_MID,
  low: SCORE_LOW,
}

const SUGGESTIONS = ['luxury feel', 'Gen-Z appeal', 'urgency', 'trustworthiness', 'cultural sensitivity']

export default function CustomMetricPanel({ diagnosticId }: Props) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<CustomMetricResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setIsLoading(true)
    setResult(null)
    const res = await getCustomMetric(diagnosticId, query.trim())
    setResult(res)
    setIsLoading(false)
  }

  const handleSuggestion = (s: string) => {
    setQuery(s)
  }

  return (
    <div className="border border-white/10 bg-panel rounded-[3px] p-7">
      <div className="mb-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-2">
          Custom Metric
        </p>
        <p className="font-sans text-sm text-white/55 max-w-lg leading-relaxed">
          Ask for any quality. Returned as AI judgment — clearly distinguished from grounded measurements.
        </p>
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2.5 mb-4">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. luxury feel, Gen-Z appeal, urgency…"
          className="flex-1 bg-noir border border-white/10 rounded-[3px] px-4 py-3 font-mono text-xs text-[#fafafa] placeholder-white/30 focus:outline-none focus:border-accent transition-colors duration-300"
          aria-label="Custom metric query"
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
          ) : 'Analyze'}
        </button>
      </form>

      {/* Suggestions */}
      <div className="flex flex-wrap gap-2 mb-6">
        {SUGGESTIONS.map(s => (
          <button
            key={s}
            type="button"
            onClick={() => handleSuggestion(s)}
            className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/40 border border-white/10 rounded-[3px] px-2.5 py-1.5
                       hover:border-accent hover:text-accent transition-colors duration-300"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Result card */}
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
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/40">not a grounded measurement</span>
            </div>
            <span
              className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] px-2.5 py-1 rounded-[3px]"
              style={{
                color: CONFIDENCE_COLOR[result.confidence],
                backgroundColor: `${CONFIDENCE_COLOR[result.confidence]}15`,
                border: `1px solid ${CONFIDENCE_COLOR[result.confidence]}30`,
              }}
            >
              {CONFIDENCE_LABEL[result.confidence]} Confidence
            </span>
          </div>

          <div className="flex items-baseline gap-4 mb-3">
            <span className="font-mono font-semibold text-4xl leading-none tracking-tightest" style={{ color: AI_GOLD }}>
              {result.score.toFixed(1)}
            </span>
            <span className="font-sans text-base font-medium text-[#fafafa] capitalize">{result.label}</span>
          </div>

          <p className="font-sans text-sm text-white/55 leading-relaxed">
            {result.reasoning}
          </p>
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
