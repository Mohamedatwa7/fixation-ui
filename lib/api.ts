// API client for F1X8
import { MOCK_RESULT } from './mock-data'
import type { DiagnosticResult, CustomMetricResult } from './mock-data'

export interface AnalysisMeta {
  title?: string
  description?: string
  format?: string
  role?: string
  mediaType?: string
}

const KPI_LABELS: Record<string, string> = {
  hook: 'Hook Strength',
  cognitive_load: 'Cognitive Load',
  pattern_interrupt: 'Pattern Interrupt',
  first_fixation: 'First Fixation',
  switching_cost: 'Switching Cost',
  anchor_stability: 'Anchor Stability',
  hierarchy: 'Visual Hierarchy',
  composition: 'Composition',
  clarity: 'Message Clarity',
  branding: 'Brand Presence',
  engagement: 'Engagement',
  attention: 'Attention',
}

function humanize(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function toKpiArray(kpis: Record<string, any> | undefined): any[] {
  if (!kpis || typeof kpis !== 'object') return []
  return Object.entries(kpis)
    .filter(([k]) => k !== 'overall' && k !== 'weights')
    .map(([k, v]) => {
      let score = 0
      let percentile: number | null = null
      let label = KPI_LABELS[k] || humanize(k)
      let citation = ''
      let methodology = ''
      if (typeof v === 'number') {
        score = v
      } else if (v && typeof v === 'object') {
        score = v.score ?? v.value ?? 0
        percentile = v.percentile ?? null
        label = v.label || label
        citation = v.research_basis || v.citation || ''
        methodology = v.methodology || v.interpretation || ''
      }
      if (score > 10) score = score / 10
      return {
        id: k,
        label,
        shortLabel: label.length > 14 ? label.split(' ')[0] : label,
        score: Number(score.toFixed(1)),
        percentile,
        citation,
        methodology,
      }
    })
}

function adaptResult(raw: any, meta: AnalysisMeta): any {
  if (!raw || typeof raw !== 'object') throw new Error('Empty response from backend')
  if (raw.error) throw new Error(raw.error)
  const diagnosis = raw.verdict && typeof raw.verdict === 'object' ? raw.verdict : {}
  const verdictText: string = typeof raw.verdict === 'string' ? raw.verdict : (diagnosis.summary || diagnosis.verdict || 'Analysis complete.')
  const risks: any[] = Array.isArray(diagnosis.risks) ? diagnosis.risks : []
  const strengths: string[] = Array.isArray(diagnosis.strengths) ? diagnosis.strengths : []
  const topRisk = risks[0] || {}
  const fix = { issue: topRisk.evidence || topRisk.issue || verdictText, action: topRisk.suggested_fix || diagnosis.recommendation || 'See detailed risks below.' }
  let score = raw.score ?? raw.kpis_overall ?? raw.kpis?.overall ?? 0
  if (score > 10) score = score / 10
  const heatmap = raw.heatmap ? `data:${raw.heatmap_type || 'image/png'};base64,${raw.heatmap}` : undefined
  return {
    id: `result-${Date.now()}`,
    title: meta.title || 'Untitled creative',
    format: (meta.format as any) || 'Social',
    role: (meta.role as any) || 'Marketer',
    mediaType: (meta.mediaType as any) || 'video',
    score: Number(Number(score).toFixed(1)),
    benchmarkPercentile: raw.benchmarkPercentile ?? raw.kpis?.percentile ?? 50,
    verdict: verdictText,
    fix,
    kpis: toKpiArray(raw.kpis),
    strengths,
    risks,
    heatmapDataUrl: heatmap,
    metadata: raw.metadata,
  }
}

export async function analyzeCreative(file: File, meta: AnalysisMeta): Promise<any> {
  const form = new FormData()
  form.append('file', file)
  if (meta.title) form.append('title', meta.title)
  if (meta.description) form.append('description', meta.description)
  if (meta.format) form.append('format_type', meta.format)
  if (meta.role) form.append('role', String(meta.role).toLowerCase().replace(/\s+/g, '_'))
  // Submit asynchronously and poll — a synchronous request holds the HTTP
  // connection open and trips Modal's web-request timeout (→ 408) on slower
  // images or cold starts. This mirrors the video flow.
  const res = await fetch('/api/analyze?endpoint=/api/analyze/image/submit', { method: 'POST', body: form })
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.error || `Analysis failed (${res.status})`) }
  const { job_id } = await res.json()
  if (!job_id) throw new Error('No job_id returned')
  let attempts = 0
  const maxAttempts = 120 // ~10 min at 5s intervals
  while (attempts < maxAttempts) {
    await new Promise(r => setTimeout(r, 5000))
    let statusRes: Response
    try { statusRes = await fetch(`/api/analyze?endpoint=/api/job/${job_id}`, { method: 'GET' }) }
    catch { attempts++; continue }
    if (!statusRes.ok) { attempts++; continue }
    const status = await statusRes.json()
    if (status.status === 'done') return adaptResult(status.result, { ...meta, mediaType: 'image' })
    if (status.status === 'error') throw new Error(`Analysis error: ${status.error}`)
    if (status.status === 'not_found') throw new Error('Job lost (backend restarted). Please resubmit.')
    attempts++
  }
  throw new Error('Image analysis timed out')
}

export async function analyzeVideoUrl(url: string, meta: AnalysisMeta): Promise<any> {
  const form = new FormData()
  form.append('url', url)
  if (meta.role) form.append('role', String(meta.role).toLowerCase().replace(/\s+/g, '_'))
  const res = await fetch('/api/analyze?endpoint=/api/analyze/video-url/submit', { method: 'POST', body: form })
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.error || `Video analysis failed (${res.status})`) }
  const { job_id } = await res.json()
  if (!job_id) throw new Error('No job_id returned')
  let attempts = 0
  const maxAttempts = 180
  while (attempts < maxAttempts) {
    await new Promise(r => setTimeout(r, 10000))
    let statusRes: Response
    try { statusRes = await fetch(`/api/analyze?endpoint=/api/job/${job_id}`, { method: 'GET' }) }
    catch { attempts++; continue }
    if (!statusRes.ok) { attempts++; continue }
    const status = await statusRes.json()
    if (status.status === 'done') return adaptResult(status.result, { ...meta, mediaType: 'video' })
    if (status.status === 'error') throw new Error(`Video analysis error: ${status.error}`)
    if (status.status === 'not_found') throw new Error('Job lost (backend restarted). Please resubmit.')
    attempts++
  }
  throw new Error('Video analysis timed out after 30 minutes')
}

/**
 * Fallback diagnostic used when the results page has no live result in memory
 * or session storage (e.g. a direct visit to /results). Returns mock data.
 */
export async function getDiagnostic(): Promise<DiagnosticResult> {
  await new Promise(r => setTimeout(r, 400))
  return MOCK_RESULT
}

/**
 * Ask for an open-ended "custom metric" judgment about a diagnostic.
 * Returned as AI judgment, clearly distinguished from grounded measurements.
 */
export async function getCustomMetric(
  _diagnosticId: string,
  query: string,
): Promise<CustomMetricResult> {
  await new Promise(r => setTimeout(r, 900))
  // Deterministic mock: derive a stable-ish score from the query length.
  const score = Number((5.5 + ((query.length * 7) % 40) / 10).toFixed(1))
  const confidence: CustomMetricResult['confidence'] =
    score >= 7.5 ? 'high' : score >= 5.5 ? 'medium' : 'low'
  return {
    label: query,
    score,
    confidence,
    reasoning:
      `Assessed "${query}" against the creative's composition, attention flow, and ` +
      `tonal cues. This is a qualitative AI judgment, not a gaze-grounded measurement, ` +
      `so weight it accordingly alongside the diagnostic KPIs.`,
  }
}
