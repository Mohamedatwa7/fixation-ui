// ─────────────────────────────────────────────────────────────────────────────
// F1X8 — types + mock diagnostic data
// All data-fetching routes through lib/api.ts.
// ─────────────────────────────────────────────────────────────────────────────

export type Role = 'Creative Director' | 'Marketer' | 'Strategist' | 'Executive'
export type MediaType = 'image' | 'video'
export type Format = 'KV' | 'OOH' | 'Banner' | 'Print' | 'Social'

export interface KPI {
  id: string
  label: string
  shortLabel: string
  score: number           // 0–10
  percentile: number | null
  citation: string
  methodology: string
}

export interface Risk {
  issue: string
  evidence?: string
  impact?: string
  suggested_fix?: string
  confidence?: string
}

export interface CustomMetricResult {
  label: string
  score: number
  confidence: 'high' | 'medium' | 'low'
  reasoning: string
}

export interface VideoMetadata {
  platform?: string
  uploader?: string
  view_count?: number
  like_count?: number
  duration_sec?: number
}

// Per-frame / per-window time series surfaced for video assets.
export interface Timelines {
  attention?: { t?: number; score: number }[]      // saliency/attention over time
  audio_energy?: { t?: number; energy: number }[]   // audio energy over time
}

export interface DiagnosticResult {
  id: string
  title: string
  format: Format
  role: Role
  mediaType: MediaType
  score: number
  /** What the headline `score` measures — 'Predicted Organic Pull' for in-feed
   *  creatives (weights calibrated vs realized engagement), else 'Engagement Potential'. */
  scoreLabel?: string
  /** Funnel-weighted craft score, shown as a secondary badge when organic pull is primary */
  craftScore?: number
  organicEngagement?: number // beta: KPI weighting calibrated vs realized organic engagement
  /** 'ranker' (fine-tuned pairwise model, holdout AUC 0.851) or 'weights' (refit KPI blend) */
  organicSource?: string
  benchmarkPercentile: number
  funnelStage?: string       // 'upper' | 'mid' | 'lower' — inferred from format (image)
  productTier?: string       // 'mass-market' | 'mid-market' | 'premium' | 'luxury'
  verdict: string
  fix: { issue: string; action: string }
  /** Detailed end-to-end remake plan (video diagnostics) */
  revisionBrief?: { objective?: string; sections: { title: string; detail: string }[] }
  /** Written analysis sections from the diagnosis (hierarchy, brand visibility, benchmark context, …) */
  analysis?: { title: string; text: string }[]
  kpis: KPI[]
  strengths: string[]
  risks: Risk[]
  heatmapDataUrl?: string
  /** Data URL preview of the uploaded creative (kept in memory only; never persisted) */
  sourcePreview?: string
  metadata?: VideoMetadata
  timelines?: Timelines
}

// ─── Fallback mock (used when no real result is stored) ──────────────────────

export const MOCK_RESULT: DiagnosticResult = {
  id: 'mock-001',
  title: 'Demo — Ramadan KV',
  format: 'KV',
  role: 'Marketer',
  mediaType: 'image',
  score: 6.4,
  benchmarkPercentile: 52,
  verdict:
    'Headline competes with product for first fixation point, splitting attention before brand association forms.',
  fix: {
    issue:
      'Your headline sits in the same high-salience zone as the product shot. Eye-tracking models predict attention splits between the two, reducing predicted dwell on the product by 31% and delaying brand association.',
    action:
      'Reduce headline font weight by one step (Bold → Medium) or reposition it below the product fold. Either change re-establishes a single dominant fixation anchor and improves message hierarchy.',
  },
  kpis: [
    {
      id: 'hierarchy',
      label: 'Visual Hierarchy',
      shortLabel: 'Hierarchy',
      score: 4.9,
      percentile: 38,
      citation: 'Tufte (1990); Lidwell et al. (2010)',
      methodology:
        'Saliency peak-to-mean ratio measures how clearly one element dominates. Three focal points of near-equal weight produce divergent scan paths.',
    },
    {
      id: 'composition',
      label: 'Composition',
      shortLabel: 'Composition',
      score: 7.1,
      percentile: 71,
      citation: 'Arnheim (1974) — Art and Visual Perception',
      methodology:
        'Rule-of-thirds alignment, visual balance, and structural tension. Product placement sits on a rule-of-thirds intersection.',
    },
    {
      id: 'white_space',
      label: 'White Space',
      shortLabel: 'White Space',
      score: 6.8,
      percentile: 60,
      citation: 'Bringhurst (2004); Williams (2014)',
      methodology:
        'White space ratio: 42% (optimal 30–50%). Slightly generous breathing room supports premium feel.',
    },
    {
      id: 'contrast',
      label: 'Color Contrast',
      shortLabel: 'Contrast',
      score: 7.2,
      percentile: 74,
      citation: 'Itti & Koch (2000) — Vision Research 40(10–12)',
      methodology:
        'Luminance contrast between key elements and background. Product-to-background contrast ratio: 5.1:1, above the 4.5:1 recommended minimum.',
    },
    {
      id: 'complexity',
      label: 'Visual Complexity',
      shortLabel: 'Complexity',
      score: 6.1,
      percentile: 55,
      citation: 'Reinecke & Gajos (2014)',
      methodology:
        'Edge density: 7.2% (optimal 4–12%). Sits within optimal range but toward the upper bound — slight risk of cognitive overload.',
    },
    {
      id: 'text_balance',
      label: 'Text / Image Balance',
      shortLabel: 'Text/Image',
      score: 5.6,
      percentile: 44,
      citation: 'Pieters & Wedel (2004) — Journal of Marketing 68(2)',
      methodology:
        'Text-overlay area vs. image area. Currently text-heavy for the KV format: 38% text vs. 25% benchmark average.',
    },
  ],
  strengths: [
    'Composition balance achieves 71st-percentile placement, with product on a rule-of-thirds intersection.',
    'Above-average color contrast (5.1:1) supports strong figure-ground separation.',
    'White space ratio (42%) within optimal range, supporting a premium visual feel.',
  ],
  risks: [
    {
      issue: 'Headline placement in primary fixation zone competes with product.',
      evidence: 'Saliency peak-to-mean ratio reduced by 38% vs. top-quartile KVs.',
      impact: 'Predicted product dwell time reduced by 31%.',
      suggested_fix: 'Reposition headline below product or reduce to Medium weight.',
      confidence: 'high',
    },
    {
      issue: 'Text-to-image ratio above benchmark average for KV format.',
      evidence: '38% text area vs. 25% category average.',
      impact: 'Increases cognitive load and reduces visual impact.',
      suggested_fix: 'Trim headline to 5–7 words and remove secondary text block.',
      confidence: 'medium',
    },
  ],
}
