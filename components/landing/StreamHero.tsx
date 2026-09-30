import Link from 'next/link'
import ImageStreamHero from '@/components/ui/image-stream-hero'

/**
 * Landing hero — the ImageStreamHero corridor in its stock presentation:
 * flat background, full-colour imagery (vivid gradients interleaved with
 * campaign-style photography), the F1X8 wordmark + slogan riding above the
 * stream and the CTA anchored below it.
 */

/* All hero art is self-hosted under /public/hero so corporate web filters
 * that block third-party CDNs (Pinterest, r2.dev) can't drop the images. */

/* Each rail renders 9 cards, so each list holds exactly 9 images and the
 * two lists share none — the rails never show the same art in parallel. */

const RIGHT_IMAGES = [
  {
    src: '/hero/diver-sunset.jpg',
    alt: 'Diver silhouetted inside a sunset seascape shaped like a profile',
  },
  {
    src: '/hero/ducati-macro.jpg',
    alt: 'Macro front view of a red Ducati superbike',
  },
  {
    src: '/hero/city-double-exposure.jpg',
    alt: 'Double-exposure portrait blended with a city skyline at dusk',
  },
  {
    src: '/hero/gradient-hero-01.png',
    alt: 'Soft multi-tone gradient wash',
  },
  {
    src: '/hero/orange-motion-portrait.jpg',
    alt: 'Motion-blurred side-profile portrait against a deep orange backdrop',
  },
  {
    src: '/hero/statue-mountain.jpg',
    alt: 'Classical statue whose face opens into a painted mountain landscape',
  },
  {
    src: '/hero/eltz-castle.jpg',
    alt: 'Eltz Castle rising out of morning mist above a mirrored reflection',
  },
  {
    src: '/hero/gradient-hue-flow.png',
    alt: 'Flowing teal-to-coral hue gradient',
  },
  {
    src: '/hero/f1-starfield.jpg',
    alt: 'Formula 1 car streaking through a starfield tunnel of light',
  },
]

const LEFT_IMAGES = [
  {
    src: '/hero/racket-cloud.jpg',
    alt: 'Figure holding a racket that dissolves into a swirling colourful cloud',
  },
  {
    src: '/hero/flower-crown-smoke.jpg',
    alt: 'Portrait with a crown of flowers exhaling a plume of smoke into a blue sky',
  },
  {
    src: '/hero/bird-hand.jpg',
    alt: 'Hand gesture with a colourful cutout of a bird flying through the fingers',
  },
  {
    src: '/hero/gradient-moon.png',
    alt: 'Pale moon-toned gradient',
  },
  {
    src: '/hero/horseback-castle.jpg',
    alt: 'First-person view on horseback charging toward a medieval castle',
  },
  {
    src: '/hero/meadow.jpg',
    alt: 'Sunlit meadow of wind-blown grass and wildflowers',
  },
  {
    src: '/hero/gradient-hero-04.png',
    alt: 'Warm layered hero gradient',
  },
  {
    src: '/hero/driver-shattered-glass.jpg',
    alt: 'Racing driver in a shattered-glass collage of light and debris',
  },
  {
    src: '/hero/leaves-prism-portrait.jpg',
    alt: 'Sunlit portrait framed by leaves and prismatic light',
  },
]

export default function StreamHero() {
  return (
    <section className="relative bg-black" aria-label="Hero">
      <ImageStreamHero
        images={RIGHT_IMAGES}
        imagesLeft={LEFT_IMAGES}
        className="h-screen min-h-[560px] w-full bg-black"
      >
        <div className="relative z-10 flex h-full flex-col items-center pb-12 text-center">
          <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 -translate-y-16 sm:-translate-y-20 md:-translate-y-24">
            <h1
              className="relative font-mono text-7xl font-bold tracking-tightest text-foreground sm:text-8xl md:text-9xl"
              aria-label="F1X8"
            >
              F<span className="text-accent">1</span>X<span className="text-accent">8</span>
              <span
                className="absolute top-1 -right-4 font-mono text-lg font-medium text-white sm:-right-5 sm:text-xl md:-right-6 md:text-2xl"
                aria-hidden="true"
              >
                ©
              </span>
            </h1>
            <p className="font-sans text-xl font-medium tracking-tight text-white/60 sm:text-2xl md:text-3xl">
              See what they see.
            </p>
          </div>
          <div className="flex flex-col items-center px-6">
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
