import Link from 'next/link'
import ImageStreamHero from '@/components/ui/image-stream-hero'

/**
 * Landing hero — the ImageStreamHero corridor in its stock presentation:
 * flat background, full-colour imagery (vivid gradients interleaved with
 * campaign-style photography), the F1X8 wordmark + slogan riding above the
 * stream and the CTA anchored below it.
 */

const CDN = 'https://pub-940ccf6255b54fa799a9b01050e6c227.r2.dev'

/* Each rail renders 9 cards, so each list holds exactly 9 images and the
 * two lists share none — the rails never show the same art in parallel. */

const RIGHT_IMAGES = [
  {
    src: `${CDN}/stock-images/767d99bb371a54d0d36751e8cecae43c.jpg`,
    alt: 'Diver silhouetted inside a sunset seascape shaped like a profile',
  },
  {
    src: 'https://i.pinimg.com/736x/80/17/36/8017367dbe52dae63b58a678018795ee.jpg',
    alt: 'Macro front view of a red Ducati superbike',
  },
  {
    src: `${CDN}/stock-images/821d815affa6496c39cbdeeec7a84603.jpg`,
    alt: 'Double-exposure portrait blended with a city skyline at dusk',
  },
  {
    src: `${CDN}/gradients/hero_gradient/hero-gradients-01.png`,
    alt: 'Soft multi-tone gradient wash',
  },
  {
    src: `${CDN}/stock-images/937438c560ada1c83317f2c11b3454b0.jpg`,
    alt: 'Motion-blurred side-profile portrait against a deep orange backdrop',
  },
  {
    src: 'https://i.pinimg.com/736x/0d/b6/1f/0db61f5245c835228df83398f6d96ceb.jpg',
    alt: 'Classical statue whose face opens into a painted mountain landscape',
  },
  {
    src: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=736&q=80',
    alt: 'Eltz Castle rising out of morning mist above a mirrored reflection',
  },
  {
    src: `${CDN}/gradients/hue-flow/hue-flow-01.png`,
    alt: 'Flowing teal-to-coral hue gradient',
  },
  {
    src: 'https://i.pinimg.com/736x/54/13/9d/54139d6fd658b1d5e71cdc07ea37a57c.jpg',
    alt: 'Formula 1 car streaking through a starfield tunnel of light',
  },
]

const LEFT_IMAGES = [
  {
    src: `${CDN}/stock-images/98f89cb9994f5c382ab964062c4039db.jpg`,
    alt: 'Figure holding a racket that dissolves into a swirling colourful cloud',
  },
  {
    src: 'https://i.pinimg.com/736x/fe/f0/8a/fef08a661d0ef55561d99a293c79dd81.jpg',
    alt: 'Portrait with a crown of flowers exhaling a plume of smoke into a blue sky',
  },
  {
    src: `${CDN}/stock-images/ddcbee38be8b7274e19e132d7ab35b53.jpg`,
    alt: 'Hand gesture with a colourful cutout of a bird flying through the fingers',
  },
  {
    src: `${CDN}/gradients/moon/moon-grade-01.png`,
    alt: 'Pale moon-toned gradient',
  },
  {
    src: 'https://i.pinimg.com/736x/39/27/f5/3927f53cebd0a148ba806fbd15e1fdd9.jpg',
    alt: 'First-person view on horseback charging toward a medieval castle',
  },
  {
    src: 'https://i.pinimg.com/736x/84/c6/10/84c610443c77c1e34398f071fdc3b71a.jpg',
    alt: 'Sunlit meadow of wind-blown grass and wildflowers',
  },
  {
    src: `${CDN}/gradients/hero_gradient/hero-gradients-04.png`,
    alt: 'Warm layered hero gradient',
  },
  {
    src: 'https://i.pinimg.com/736x/a9/4c/e0/a94ce014127cfded1c7160b110eb7a86.jpg',
    alt: 'Racing driver in a shattered-glass collage of light and debris',
  },
  {
    src: 'https://i.pinimg.com/736x/2d/0b/74/2d0b74227b38d56fcc8b9f4872addcfc.jpg',
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
