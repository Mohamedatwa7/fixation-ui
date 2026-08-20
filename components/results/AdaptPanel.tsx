'use client'
import { useState } from 'react'
import { adaptCreative, analyzeCreative } from '@/lib/api'
import { setLastResult } from '@/lib/resultStore'
import type { DiagnosticResult } from '@/lib/mock-data'

type Phase = 'idle' | 'generating' | 'done' | 'rescoring'

const blobToDataUrl = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = reject
    r.readAsDataURL(blob)
  })

export default function AdaptPanel({ result }: { result: DiagnosticResult }) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [revisedUrl, setRevisedUrl] = useState<string | null>(null)
  const [prompt, setPrompt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const applicable = result.mediaType === 'image' && result.risks.some(r => r.suggested_fix)
  if (!applicable) return null
  const hasSource = Boolean(result.sourcePreview)

  const generate = async () => {
    setError(null)
    setPhase('generating')
    try {
      const { url, prompt } = await adaptCreative(result)
      setRevisedUrl(url)
      setPrompt(prompt)
      setPhase('done')
    } catch (e: any) {
      setError(e?.message || 'Revision failed')
      setPhase('idle')
    }
  }

  const rescore = async () => {
    if (!revisedUrl) return
    setError(null)
    setPhase('rescoring')
    try {
      const blob = await fetch(revisedUrl).then(r => r.blob())
      const file = new File([blob], 'revised-kv.png', { type: blob.type || 'image/png' })
      const sourcePreview = await blobToDataUrl(blob)
      let next = await analyzeCreative(file, {
        title: `${result.title} — revised`,
        format: result.format,
        role: String(result.role),
        mediaType: 'image',
      })
      next = { ...next, sourcePreview }
      setLastResult(next)
      try {
        sessionStorage.setItem('f1x8_result', JSON.stringify({ ...next, heatmapDataUrl: undefined, sourcePreview: undefined }))
      } catch {}
      window.location.reload()
    } catch (e: any) {
      setError(e?.message || 'Rescore failed')
      setPhase('done')
    }
  }

  const busy = phase === 'generating' || phase === 'rescoring'

  return (
    <div className="bg-panel border border-white/10 rounded-[3px]">
      <div className="p-7">
        <div className="flex items-center justify-between mb-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40">
            Revised KV — Higgsfield
          </p>
          {phase === 'done' && revisedUrl && (
            <a
              href={revisedUrl}
              download="revised-kv.png"
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/55 hover:text-accent transition-colors duration-300"
            >
              Download
            </a>
          )}
        </div>

        <p className="font-sans text-sm text-white/65 leading-relaxed mb-5">
          Apply this diagnostic&apos;s suggested fixes to the original creative as an
          image-to-image edit, then rescore the result to verify the lift.
        </p>

        {phase === 'done' && revisedUrl && result.sourcePreview && (
          <div className="grid grid-cols-2 gap-3 mb-5">
            {[
              { label: 'Original', src: result.sourcePreview },
              { label: 'Revised', src: revisedUrl },
            ].map(({ label, src }) => (
              <figure key={label}>
                <figcaption className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">
                  {label}
                </figcaption>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src} alt={`${label} creative`} className="w-full rounded-[2px] border border-white/10" />
              </figure>
            ))}
          </div>
        )}

        {error && (
          <p className="font-mono text-[11px] text-[#ff4f23] mb-4">{error}</p>
        )}

        <div className="flex items-center gap-4">
          <button
            onClick={phase === 'done' ? rescore : generate}
            disabled={busy || !hasSource}
            className="font-mono text-[10px] uppercase tracking-[0.18em] px-4 py-2.5 rounded-[2px] border border-white/10 text-white/55 hover:text-accent hover:border-white/25 transition-colors duration-300 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {phase === 'generating' && 'Generating revision…'}
            {phase === 'rescoring' && 'Rescoring revision…'}
            {phase === 'idle' && 'Generate revised KV'}
            {phase === 'done' && 'Rescore revised KV'}
          </button>
          {busy && (
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none" className="animate-spin text-accent">
              <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
                strokeDasharray="28" strokeDashoffset="10" />
            </svg>
          )}
          {!hasSource && (
            <span className="font-mono text-[10px] text-white/40">
              Original image unavailable — run a new diagnostic to enable revision.
            </span>
          )}
        </div>

        {phase === 'done' && prompt && (
          <details className="mt-5">
            <summary className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 cursor-pointer hover:text-white/60">
              Edit prompt
            </summary>
            <p className="font-mono text-[11px] text-white/50 leading-relaxed mt-3 whitespace-pre-wrap">{prompt}</p>
          </details>
        )}
      </div>
    </div>
  )
}
