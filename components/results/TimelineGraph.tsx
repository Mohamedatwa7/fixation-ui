'use client'
import { useRef, useState } from 'react'

// Lightweight inline SVG line chart for video signal timelines (attention,
// audio energy). No charting dependency — just a normalized polyline + area fill,
// styled for the dark "instrument" results theme. Axis labels and the hover
// readout are HTML overlays: the SVG is stretched (preserveAspectRatio="none"),
// so anything drawn inside it would distort.
interface Props {
  title: string
  values: number[]
  /** Timestamps (seconds) matching `values`; used for the x-axis and hover readout */
  times?: number[]
  color: string
  fixedMax?: number   // e.g. 10 for the 0–10 attention scale; omit to auto-scale
  caption?: string
}

function fmtT(sec: number): string {
  return sec >= 60 ? `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}` : `${Number(sec.toFixed(1))}s`
}

export default function TimelineGraph({ title, values, times, color, fixedMax, caption }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)

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

  const yLabel = (v: number) => (fixedMax ? String(Math.round(v)) : Number(v.toFixed(1)).toString())
  const hasTimes = !!times && times.length === n && times.every(t => typeof t === 'number' && isFinite(t))
  const tStart = hasTimes ? times![0] : 0
  const tEnd = hasTimes ? times![n - 1] : n - 1
  const xLabel = (frac: number) =>
    hasTimes ? fmtT(tStart + frac * (tEnd - tStart)) : String(Math.round(frac * (n - 1)))

  const onMove = (e: React.MouseEvent) => {
    const el = chartRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    setHover(Math.round(frac * (n - 1)))
  }

  // Hover marker position as percentages of the plot box (matches the
  // stretched SVG coordinate space).
  const hx = hover !== null ? (xAt(hover) / W) * 100 : 0
  const hy = hover !== null ? (yAt(pts[hover]) / H) * 100 : 0
  const hoverOnRight = hover !== null && hover > (n - 1) / 2

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40">{title}</p>
        {caption && <span className="font-mono text-[10px] text-white/30">{caption}</span>}
      </div>

      <div className="flex gap-2">
        {/* Y axis */}
        <div
          className="flex h-20 flex-col justify-between items-end py-0.5 font-mono text-[9px] tabular-nums text-white/35 select-none w-6 flex-shrink-0"
          aria-hidden="true"
        >
          <span>{yLabel(max)}</span>
          <span>{yLabel(min + span / 2)}</span>
          <span>{yLabel(min)}</span>
        </div>

        {/* Plot column */}
        <div className="flex-1 min-w-0">
          {/* Hover overlays live in this wrapper so their percentage offsets
              map onto the SVG box alone — including the x-axis row below
              shifted the dot off the line. */}
          <div
            ref={chartRef}
            className="relative cursor-crosshair"
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
          >
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
            {/* Horizontal gridlines at min / mid / max */}
            {[yAt(min), yAt(min + span / 2), yAt(max)].map(y => (
              <line
                key={y}
                x1={PAD} x2={W - PAD} y1={y} y2={y}
                stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" vectorEffect="non-scaling-stroke"
              />
            ))}
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

          {/* Hover crosshair + dot + readout */}
          {hover !== null && (
            <>
              <div
                className="absolute top-0 bottom-0 w-px bg-white/25 pointer-events-none"
                style={{ left: `${hx}%` }}
                aria-hidden="true"
              />
              <div
                className="absolute w-2 h-2 rounded-full border border-noir pointer-events-none -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${hx}%`, top: `${hy}%`, backgroundColor: color }}
                aria-hidden="true"
              />
              <div
                className={`absolute top-1.5 pointer-events-none bg-elevated border border-white/15 rounded-[2px] px-2 py-1
                            font-mono text-[10px] tabular-nums whitespace-nowrap ${hoverOnRight ? '-translate-x-full' : ''}`}
                style={hoverOnRight ? { left: `calc(${hx}% - 6px)` } : { left: `calc(${hx}% + 6px)` }}
              >
                <span style={{ color }}>{Number(pts[hover].toFixed(2))}</span>
                {hasTimes && <span className="text-white/40"> · {fmtT(times![hover])}</span>}
              </div>
            </>
          )}
          </div>

          {/* X axis */}
          <div
            className="flex justify-between pt-1 font-mono text-[9px] tabular-nums text-white/35 select-none"
            aria-hidden="true"
          >
            <span>{xLabel(0)}</span>
            <span>{xLabel(0.25)}</span>
            <span>{xLabel(0.5)}</span>
            <span>{xLabel(0.75)}</span>
            <span>{xLabel(1)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
