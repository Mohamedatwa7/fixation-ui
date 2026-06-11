/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        accent: '#ff4f23',     // brand pop + low-score alert
        noir: '#0a0a0a',       // app background (true near-black) — not "base" (collides with text-base)
        panel: '#141414',      // card / panel surface
        elevated: '#1c1c1c',   // hover / raised surface
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
