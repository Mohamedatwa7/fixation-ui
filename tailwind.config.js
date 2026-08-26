/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        accent: '#e0e0e0',     // halide silver — brand chrome (score alert colors stay in lib/score.ts)
        noir: '#0a0a0a',       // app background (true near-black) — not "base" (collides with text-base)
        panel: '#141414',      // card / panel surface
        elevated: '#1c1c1c',   // hover / raised surface
        // shadcn-style tokens so components/ui/* can use their stock classes
        background: '#0a0a0a',
        foreground: '#fafafa',
        border: 'rgba(255, 255, 255, 0.1)',
        muted: {
          DEFAULT: '#141414',
          foreground: '#a1a1a1',
        },
      },
      fontFamily: {
        // Geist Mono is the hero/display + label/data face (console aesthetic)
        mono: ['var(--font-geist-mono)', 'JetBrains Mono', 'Courier New', 'monospace'],
        // Geist Sans for longer body copy / readability
        sans: ['var(--font-geist-sans)', 'Inter', '-apple-system', 'sans-serif'],
      },
      letterSpacing: {
        tightest: '-0.04em',
      },
      transitionTimingFunction: {
        cinematic: 'cubic-bezier(0.215, 0.61, 0.355, 1)',
      },
    },
  },
  plugins: [],
}
