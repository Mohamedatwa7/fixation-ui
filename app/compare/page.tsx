'use client'
import { useState } from 'react'
import Nav from '@/components/Nav'
import { SCORE_HIGH, SCORE_MID, SCORE_LOW } from '@/lib/score'

const AI_GOLD = SCORE_MID

interface CompareItem {
  file: File
  preview: string
  b64: string
  mediaType: string
}

interface CompareResult {
  winner_index: number
  ranking: { index: number; label: string; rank_score: number }[]
  explanation: {
    why_winner: string
    per_creative: { index: number; read: string }[]
    what_would_flip_it: string
    caveat: string
  }
  model_note?: string
  error?: string
}

async function fileToB64(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer())
  let s = ''
  for (let i = 0; i < buf.length; i += 0x8000) {
    s += String.fromCharCode(...buf.subarray(i, i + 0x8000))
  }
  return btoa(s)
}

export default function ComparePage() {
  const [items, setItems] = useState<CompareItem[]>([])
  const [description, setDescription] = useState('')
  const [format, setFormat] = useState('Social')
  const [result, setResult] = useState<CompareResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const addFiles = async (files: FileList | null) => {
    if (!files) return
    const next: CompareItem[] = [...items]
    for (const f of Array.from(files)) {
      if (!f.type.startsWith('image/') || next.length >= 3) continue
      next.push({
        file: f,
        preview: URL.createObjectURL(f),
        b64: await fileToB64(f),
        mediaType: f.type,
      })
    }
    setItems(next.slice(0, 3))
    setResult(null)
    setError(null)
  }

  const run = async () => {
    if (items.length < 2 || loading) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await fetch('/api/analyze?endpoint=/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: items.map((it, i) => ({
            image_b64: it.b64,
            media_type: it.mediaType,
            label: `Option ${String.fromCharCode(65 + i)}`,
          })),
          description: description || undefined,
          format_type: format,
        }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `Compare failed (${res.status})`)
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Comparison failed.')
    } finally {
      setLoading(false)
    }
  }

  const scoreFor = (i: number) =>
    result?.ranking.find(r => r.index === i)?.rank_score

  return (
    <main className="min-h-screen bg-noir text-[#fafafa]">
      <Nav />
      <div className="mx-auto max-w-5xl px-6 pt-28 pb-20">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-3">
          Pick the winner
        </p>
        <h1 className="font-mono text-3xl font-semibold tracking-tightest mb-3">
          Which creative should run?
        </h1>
        <p className="font-sans text-sm text-white/55 max-w-xl leading-relaxed mb-10">
          Upload 2–3 options. The ranking model — validated against real market
          outcomes, where it picks the better-performing creative 92% of the
          time — orders them, and the diagnosis engine explains the call.
        </p>

        {/* Upload slots */}
        <div className="grid gap-4 sm:grid-cols-3 mb-6">
          {[0, 1, 2].map(i => (
            <div key={i}
              className="relative border border-white/10 bg-panel rounded-[3px] aspect-[4/5] overflow-hidden flex items-center justify-center">
              {items[i] ? (
                <>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={items[i].preview} alt={`Option ${String.fromCharCode(65 + i)}`}
                    className="h-full w-full object-contain" />
                  <span className="absolute top-2 left-2 font-mono text-[10px] uppercase tracking-[0.16em] bg-noir/80 border border-white/15 rounded-[3px] px-2 py-1">
                    Option {String.fromCharCode(65 + i)}
                  </span>
                  {result && scoreFor(i) !== undefined && (
                    <span
                      className="absolute top-2 right-2 font-mono text-sm font-semibold rounded-[3px] px-2 py-1"
                      style={{
                        color: result.winner_index === i ? SCORE_HIGH : 'rgba(255,255,255,0.6)',
                        backgroundColor: 'rgba(10,10,10,0.85)',
                        border: `1px solid ${result.winner_index === i ? SCORE_HIGH : 'rgba(255,255,255,0.15)'}`,
                      }}>
                      {scoreFor(i)?.toFixed(1)}
                    </span>
                  )}
                  {result && result.winner_index === i && (
                    <span className="absolute bottom-2 left-2 font-mono text-[10px] font-medium uppercase tracking-[0.16em] px-2 py-1 rounded-[3px]"
                      style={{ color: '#0a0a0a', backgroundColor: SCORE_HIGH }}>
                      Winner
                    </span>
                  )}
                  <button type="button"
                    onClick={() => { setItems(items.filter((_, j) => j !== i)); setResult(null) }}
                    className="absolute bottom-2 right-2 font-mono text-[10px] text-white/40 hover:text-white border border-white/10 rounded-[3px] px-2 py-1 bg-noir/80">
                    remove
                  </button>
                </>
              ) : (
                <label className="cursor-pointer text-center p-6 w-full h-full flex flex-col items-center justify-center hover:bg-white/[0.02] transition-colors">
                  <span className="font-mono text-2xl text-white/25 mb-2">+</span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/35">
                    Add option {String.fromCharCode(65 + i)}
                  </span>
                  <input type="file" accept="image/*" multiple className="hidden"
                    onChange={e => addFiles(e.target.files)} />
                </label>
              )}
            </div>
          ))}
        </div>

        {/* Context + run */}
        <div className="flex flex-wrap gap-2.5 mb-10">
          <select value={format} onChange={e => setFormat(e.target.value)}
            className="bg-panel border border-white/10 rounded-[3px] px-3 py-3 font-mono text-xs text-white/70 focus:outline-none focus:border-accent">
            {['KV', 'Social', 'Banner', 'OOH', 'Print'].map(f => <option key={f}>{f}</option>)}
          </select>
          <input type="text" value={description} onChange={e => setDescription(e.target.value)}
            placeholder="campaign context (optional)"
            className="flex-1 min-w-[200px] bg-panel border border-white/10 rounded-[3px] px-4 py-3 font-mono text-xs placeholder-white/30 focus:outline-none focus:border-accent" />
          <button type="button" onClick={run} disabled={items.length < 2 || loading}
            className="px-6 py-3 bg-[#fafafa] text-[#0a0a0a] text-[10px] font-mono uppercase tracking-[0.16em] rounded-[3px] hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {loading ? 'Ranking…' : 'Pick the winner'}
          </button>
        </div>

        {loading && (
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/35 mb-6">
            Scoring with the outcome-validated ranker, then writing the rationale — ~30s…
          </p>
        )}
        {error && <p className="font-sans text-sm mb-6" style={{ color: SCORE_LOW }}>{error}</p>}

        {result && (
          <div className="border border-white/10 bg-panel rounded-[3px] p-7 space-y-6">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">
                Why {result.ranking[0]?.label} wins
              </p>
              <p className="font-sans text-sm text-white/65 leading-relaxed">
                {result.explanation.why_winner}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {result.explanation.per_creative.map(pc => (
                <div key={pc.index} className="border border-white/10 bg-noir/60 rounded-[3px] p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/40 mb-1.5">
                    Option {String.fromCharCode(65 + pc.index)}
                  </p>
                  <p className="font-sans text-xs text-white/55 leading-snug">{pc.read}</p>
                </div>
              ))}
            </div>
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">
                What would flip it
              </p>
              <p className="font-sans text-sm text-white/60 leading-relaxed">
                {result.explanation.what_would_flip_it}
              </p>
            </div>
            <div className="flex items-start gap-2.5 pt-1">
              <span className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] px-2.5 py-1 rounded-[3px] border shrink-0"
                style={{ color: AI_GOLD, backgroundColor: `${AI_GOLD}1f`, borderColor: `${AI_GOLD}40` }}>
                ⚠ Note
              </span>
              <p className="font-sans text-xs text-white/40 leading-snug">
                {result.explanation.caveat} {result.model_note}
              </p>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
