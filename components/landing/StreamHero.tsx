import Link from 'next/link'
import ImageStreamHero from '@/components/ui/image-stream-hero'

/**
 * Landing hero — the ImageStreamHero corridor in its stock presentation:
 * flat background, full-colour imagery (vivid gradients interleaved with
 * campaign-style photography), headline riding above the stream and the
 * supporting line + CTA anchored below it.
 */

const CDN = 'https://pub-940ccf6255b54fa799a9b01050e6c227.r2.dev'

const STREAM_IMAGES = [
  {
    src: `${CDN}/stock-images/767d99bb371a54d0d36751e8cecae43c.jpg`,
    alt: 'Diver silhouetted inside a sunset seascape shaped like a profile',
  },
  {
    src: `${CDN}/gradients/hero_gradient/hero-gradients-01.png`,
    alt: 'Soft multi-tone gradient wash',
  },
  {
    src: `${CDN}/stock-images/821d815affa6496c39cbdeeec7a84603.jpg`,
    alt: 'Double-exposure portrait blended with a city skyline at dusk',
  },
  {
    src: `${CDN}/gradients/crimson_aura/crimson-aura-02.png`,
    alt: 'Crimson aura gradient',
  },
  {
    src: `${CDN}/stock-images/937438c560ada1c83317f2c11b3454b0.jpg`,
    alt: 'Motion-blurred side-profile portrait against a deep orange backdrop',
  },
  {
    src: `${CDN}/gradients/hue-flow/hue-flow-01.png`,
    alt: 'Flowing hue gradient',
  },
  {
    src: `${CDN}/stock-images/98f89cb9994f5c382ab964062c4039db.jpg`,
    alt: 'Figure holding a racket that dissolves into a swirling colourful cloud',
  },
  {
    src: `${CDN}/gradients/moon/moon-grade-03.png`,
    alt: 'Moon-toned gradient',
  },
  {
    src: `${CDN}/stock-images/ddcbee38be8b7274e19e132d7ab35b53.jpg`,
    alt: 'Hand gesture with a colourful cutout of a bird flying through the fingers',
  },
  {
    src: `${CDN}/gradients/hero_gradient/hero-gradients-03.png`,
    alt: 'Layered hero gradient',
  },
  {
    src: `${CDN}/gradients/hue-flow/hue-flow-02.png`,
    alt: 'Second flowing hue gradient',
  },
  {
    src: `${CDN}/gradients/moon/moon-grade-05.png`,
    alt: 'Deep moon-toned gradient',
  },
]

export default function StreamHero() {
  return (
    <section className="relative bg-background pt-16" aria-label="Hero">
      <ImageStreamHero
        images={STREAM_IMAGES}
        className="h-[calc(100vh-4rem)] min-h-[560px] w-full bg-background"
      >
        <div className="relative z-10 flex h-full flex-col items-center justify-between py-12 text-center">
          <div className="px-6">
            <h1 className="text-balance text-4xl font-medium tracking-tight text-foreground sm:text-5xl md:text-6xl">
              See what
              <br />
              they see.
            </h1>
          </div>
          <div className="flex flex-col items-center gap-6 px-6">
            <p className="max-w-md text-balance text-sm text-muted-foreground">
              F1X8 maps attention before launch — every creative in the stream
              has been through the diagnostic engine. Run yours and see where
              the eyes actually go.
            </p>
            <Link
              href="/upload"
              className="group inline-flex items-center gap-3 bg-accent text-[#0a0a0a] font-mono text-[11px]
                         font-medium uppercase tracking-[0.18em] px-8 py-4 rounded-[3px]
                         hover:bg-white transition-colors duration-300 ease-cinematic
                         shadow-[0_0_40px_-8px_rgba(224,224,224,0.35)]"
            >
              Run a diagnostic
              <ArrowRight />
            </Link>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/35">
              No account required · Results in &lt; 30s
            </span>
          </div>
        </div>
      </ImageStreamHero>
    </section>
  )
}

function ArrowRight() {
  return (
    <svg width="16" height="12" viewBox="0 0 16 12" fill="none" aria-hidden="true"
      className="transition-transform duration-300 ease-cinematic group-hover:translate-x-1">
      <path d="M1 6h13M10 1l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
