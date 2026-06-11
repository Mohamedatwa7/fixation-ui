import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import './globals.css'

export const metadata: Metadata = {
  title: 'F1X8 — Creative Diagnostics',
  description: 'Cognitive-science attention diagnostics for video and static creative.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistMono.variable} ${GeistSans.variable}`}>
      <body className="font-mono bg-[#0a0a0a] text-[#fafafa]">{children}</body>
    </html>
  )
}
