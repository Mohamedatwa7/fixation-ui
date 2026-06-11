/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        accent: '#ff4f23',     // depoluxe orange-red — brand pop + alert
        paper: '#f3f0ea',      // warm off-white (light editorial bg)
        ink: '#100f0c',        // near-black (light text / dark base)
      },
      fontFamily: {
        serif: ['var(--font-serif)', 'EB Garamond', 'Georgia', 'serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'Courier New', 'monospace'],
        sans: ['var(--font-sans)', 'Inter', '-apple-system', 'sans-serif'],
      },
      letterSpacing: {
        tightest: '-0.02em',
      },
      transitionTimingFunction: {
        cinematic: 'cubic-bezier(0.215, 0.61, 0.355, 1)',  // ease-out-cubic
      },
    },
  },
  plugins: [],
}
