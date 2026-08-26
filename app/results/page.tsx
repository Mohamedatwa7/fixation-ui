'use client'
import { getLastResult } from '@/lib/resultStore'
import { useEffect, useState } from 'react'
import Nav from '@/components/Nav'
import SpecimenVerdict from '@/components/results/SpecimenVerdict'
import FixCard from '@/components/results/FixCard'
import KpiStrip from '@/components/results/KpiStrip'
import CustomMetricPanel from '@/components/results/CustomMetricPanel'
import AdaptPanel from '@/components/results/AdaptPanel'
import FullDiagnostic from '@/components/results/FullDiagnostic'
import ExportButton from '@/components/results/ExportButton'
import { getDiagnostic } from '@/lib/api'
import type { DiagnosticResult, VideoMetadata } from '@/lib/mock-data'
import Link from 'next/link'

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

function fmtDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = String(sec % 60).padStart(2, '0')
  return `${m}:${s}`
}

function VideoMetadataStrip({ meta }: { meta: VideoMetadata }) {
  const items: { label: string; value: string }[] = []
  if (meta.platform) items.push({ label: 'Platform', value: meta.platform })
  if (meta.uploader) items.push({ label: 'Uploader', value: meta.uploader })
  if (meta.view_count != null) items.push({ label: 'Views', value: fmtCount(meta.view_count) })
  if (meta.like_count != null) items.push({ label: 'Likes', value: fmtCount(meta.like_count) })
  if (meta.duration_sec != null) items.push({ label: 'Duration', value: fmtDuration(meta.duration_sec) })
  if (items.length === 0) return null

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-2 px-5 py-4 bg-panel border border-white/10 rounded-[3px]">
      {items.map(({ label, value }) => (
        <div key={label} className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40">{label}</span>
          <span className="font-mono text-xs text-[#fafafa]">{value}</span>
        </div>
      ))}
    </div>
  )
}

export default function ResultsPage() {
  const [result, setResult] = useState<DiagnosticResult | null>(null)

  useEffect(() => {
    const inMemory = getLastResult()
    if (inMemory) { setResult(inMemory); return }
    const stored = sessionStorage.getItem('f1x8_result')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed && Array.isArray(parsed.kpis) && typeof parsed.score === 'number') {
          setResult(parsed)
          return
        }
      } catch {}
    }
    getDiagnostic().then(setResult)
  }, [])

  if (!result) {
    return (
      <main className="bg-noir min-h-screen text-[#fafafa]">
        <Nav active="results" />
        <div className="pt-16 min-h-screen flex items-center justify-center">
          <div className="flex items-center gap-3">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin text-accent">
              <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
                strokeDasharray="28" strokeDashoffset="10" />
            </svg>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/45">Loading diagnostic…</span>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="relative bg-noir min-h-screen text-[#fafafa]">
      <Nav active="results" />
      <div className="absolute inset-0 bg-grid pointer-events-none" aria-hidden="true" />

      <div className="relative pt-16 px-4 sm:px-6 py-12">
        <div className="max-w-4xl mx-auto space-y-5">

          {/* Breadcrumb */}
          <div className="flex items-center gap-2.5 pb-2">
            <Link
              href="/upload"
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/40 hover:text-accent transition-colors duration-300"
            >
              ← New diagnostic
            </Link>
            {result.title && (
              <>
                <span className="font-mono text-[10px] text-white/20">/</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/55">{result.title}</span>
              </>
            )}
            <div className="ml-auto">
              <ExportButton result={result} />
            </div>
          </div>

          {result.metadata && <VideoMetadataStrip meta={result.metadata} />}
          <SpecimenVerdict result={result} />
          <FixCard fix={result.fix} revisionBrief={result.revisionBrief} />

          <section aria-label="Revised KV generation">
            <AdaptPanel result={result} />
          </section>

          <section aria-label="KPI diagnostics">
            <KpiStrip kpis={result.kpis} />
          </section>

          <section aria-label="Custom metric analysis">
            <CustomMetricPanel diagnosticId={result.id} />
          </section>

          <section aria-label="Full diagnostic details">
            <FullDiagnostic result={result} />
          </section>

        </div>
      </div>
    </main>
  )
}
