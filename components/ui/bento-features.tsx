import React from 'react'

/* Adapted from 21st.dev "bento-features": the golden-angle dot spiral and the
 * bento card, retyped for TS and restyled to the F1X8 instrument theme
 * (Geist Mono labels, rounded-[3px], border-white/10). The demo section and
 * its marketing copy were dropped — pages compose these primitives directly. */

export interface DotSpiralProps {
  points?: number
  dotRadius?: number
  /** Seconds for one pulse cycle */
  duration?: number
  color?: string
  pulse?: boolean
  opacityMin?: number
  opacityMax?: number
  sizeMin?: number
  sizeMax?: number
  /** SVG square size in px */
  size?: number
  className?: string
}

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5))

export function DotSpiral({
  points = 800,
  dotRadius = 1.6,
  duration = 3,
  color = '#ffffff',
  pulse = true,
  opacityMin = 0.25,
  opacityMax = 0.9,
  sizeMin = 0.5,
  sizeMax = 1.35,
  size = 620,
  className,
}: DotSpiralProps) {
  const center = size / 2
  const maxR = center - 4 - dotRadius

  const dots = Array.from({ length: points }, (_, i) => {
    const idx = i + 0.5
    const frac = idx / points
    const r = Math.sqrt(frac) * maxR
    const theta = idx * GOLDEN_ANGLE
    return {
      x: +(center + r * Math.cos(theta)).toFixed(3),
      y: +(center + r * Math.sin(theta)).toFixed(3),
      begin: +(frac * duration).toFixed(3),
    }
  })

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      aria-hidden="true"
    >
      {dots.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r={dotRadius} fill={color} opacity={0.6}>
          {pulse && (
            <>
              <animate
                attributeName="r"
                values={`${dotRadius * sizeMin};${dotRadius * sizeMax};${dotRadius * sizeMin}`}
                dur={`${duration}s`}
                begin={`${d.begin}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="opacity"
                values={`${opacityMin};${opacityMax};${opacityMin}`}
                dur={`${duration}s`}
                begin={`${d.begin}s`}
                repeatCount="indefinite"
              />
            </>
          )}
        </circle>
      ))}
    </svg>
  )
}

export interface BentoCardProps {
  title: string
  blurb?: string
  meta?: string
  /** Tailwind col/row span classes, e.g. "md:col-span-4 md:row-span-2" */
  span?: string
  children?: React.ReactNode
  className?: string
}

export function BentoCard({ title, blurb, meta, span = '', children, className = '' }: BentoCardProps) {
  return (
    <article
      className={`group relative overflow-hidden rounded-[3px] border border-white/10 bg-panel p-5
                  transition-colors duration-300 hover:border-white/30 ${span} ${className}`}
    >
      <header className="mb-2.5 flex items-center gap-3">
        <span className="font-mono text-xs text-accent" aria-hidden="true">
          ●
        </span>
        <h3 className="font-mono text-sm font-semibold tracking-tight text-[#fafafa] leading-tight">
          {title}
        </h3>
        {meta && (
          <span className="ml-auto rounded-full border border-white/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-white/55">
            {meta}
          </span>
        )}
      </header>
      {blurb && <p className="font-sans text-[13px] text-white/50 leading-relaxed max-w-prose">{blurb}</p>}
      {children}
    </article>
  )
}
