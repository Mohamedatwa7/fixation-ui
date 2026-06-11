import type { Metadata } from 'next'
import { JetBrains_Mono, Inter, EB_Garamond } from 'next/font/google'
import './globals.css'

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600'],
})

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  weight: ['400', '500', '600'],
})

const ebGaramond = EB_Garamond({
  subsets: ['latin'],
  variable: '--font-serif',
  weight: ['400', '500', '600'],
  style: ['normal', 'italic'],
})

export const metadata: Metadata = {
  title: 'F1X8 — Creative Diagnostics',
  description: 'Cognitive-science attention diagnostics for video and static creative.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${ebGaramond.variable} ${jetbrainsMono.variable} ${inter.variable}`}>
      <body className="font-serif bg-paper text-ink">{children}</body>
    </html>
  )
}
