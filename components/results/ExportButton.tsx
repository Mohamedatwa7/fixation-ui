'use client'
import { useState } from 'react'
import type { DiagnosticResult } from '@/lib/mock-data'
import { exportResultToPdf } from '@/lib/exportPdf'

export default function ExportButton({ result }: { result: DiagnosticResult }) {
  const [busy, setBusy] = useState(false)

  function handleExport() {
    setBusy(true)
    try {
      exportResultToPdf(result)
    } finally {
      // The print window owns the rest; release the button shortly after.
      setTimeout(() => setBusy(false), 1500)
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={busy}
      aria-label="Export full diagnostic as PDF"
      className="group flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-white/55 border border-white/10 px-3 py-1.5 rounded-[2px] hover:text-accent hover:border-accent/40 transition-colors duration-300 disabled:opacity-50 disabled:cursor-wait focus:outline-none focus:ring-1 focus:ring-accent"
    >
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true"
        className="text-current">
        <path d="M6 1v6m0 0L3.5 4.7M6 7l2.5-2.3M2 8.5v1.5a.5.5 0 0 0 .5.5h7a.5.5 0 0 0 .5-.5V8.5"
          stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {busy ? 'Preparing…' : 'Export PDF'}
    </button>
  )
}
