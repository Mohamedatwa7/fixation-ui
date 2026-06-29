// Lightweight inline SVG line chart for video signal timelines (attention,
// audio energy). No charting dependency — just a normalized polyline + area fill,
// styled for the dark "instrument" results theme.
interface Props {
  title: string
  values: number[]
  color: string
  fixedMax?: number   // e.g. 10 for the 0–10 attention scale; omit to auto-scale
  caption?: string
}

export default function TimelineGraph({ title, values, color, fixedMax, caption }: Props) {
  const pts = (values || []).filter(v => typeof v === 'number' && isFinite(v))
  if (pts.length < 2) return null

  const W = 100
  const H = 30
  const PAD = 2
  const max = fixedMax ?? Math.max(...pts)
  const min = fixedMax ? 0 : Math.min(...pts)
  const span = max - min || 1
  const n = pts.length
  const xAt = (i: number) => PAD + (i / (n - 1)) * (W - 2 * PAD)
  const yAt = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD)

  const line = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${xAt(i).toFixed(2)},${yAt(v).toFixed(2)}`).join(' ')
  const area = `${line} L${xAt(n - 1).toFixed(2)},${H - PAD} L${xAt(0).toFixed(2)},${H - PAD} Z`
  const gradId = `tl-${title.replace(/\W/g, '')}`

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40">{title}</p>
        {caption && <span className="font-mono text-[10px] text-white/30">{caption}</span>}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full h-20 block rounded-[2px] border border-white/10 bg-black/30"
        role="img"
        aria-label={title}
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#${gradId})`} />
        <path
          d={line}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}
