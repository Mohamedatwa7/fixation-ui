'use client'
import { useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Nav from '@/components/Nav'
import { analyzeCreative, analyzeVideoUrl } from '@/lib/api'
import { setLastResult } from '@/lib/resultStore'

const ROLES = ['Creative Director', 'Marketer', 'Strategist', 'Executive'] as const
const IMAGE_FORMATS = ['KV', 'OOH', 'Banner', 'Print', 'Social'] as const
const VIDEO_FORMATS = ['TVC', 'Pre-roll', 'Bumper', 'Story', 'Reel', 'Social'] as const
type Role = typeof ROLES[number]
type Format = typeof IMAGE_FORMATS[number] | typeof VIDEO_FORMATS[number]
type InputMode = 'upload' | 'url'

const LOADING_STEPS = [
  'Uploading creative…',
  'Mapping attention zones…',
  'Running benchmark comparison…',
  'Computing KPI scores…',
  'Generating diagnosis…',
]

const URL_LOADING_STEPS = [
  'Fetching from URL…',
  'Mapping attention zones…',
  'Running benchmark comparison…',
  'Computing KPI scores…',
  'Generating diagnosis…',
]

async function fileFromUrl(url: string, mediaType: 'image' | 'video'): Promise<File> {
  const res = await fetch('/api/fetch-url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Failed to fetch URL' }))
    throw new Error(err.error ?? 'Failed to fetch URL')
  }
  const blob = await res.blob()
  // Fall back to a sensible MIME type if the server didn't set Content-Type
  const mime = blob.type || (mediaType === 'video' ? 'video/mp4' : 'image/jpeg')
  const name = url.split('/').pop()?.split('?')[0] || (mediaType === 'video' ? 'creative.mp4' : 'creative.jpg')
  return new File([blob], name, { type: mime })
}

export default function UploadPage() {
  const router = useRouter()
  const [mediaType, setMediaType] = useState<'image' | 'video'>('image')
  const [inputMode, setInputMode] = useState<InputMode>('upload')
  const [role, setRole] = useState<Role>('Marketer')
  const [format, setFormat] = useState<Format>('KV')
  const [title, setTitle] = useState('')
  const [context, setContext] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [mediaUrl, setMediaUrl] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) { setFile(dropped); setError(null) }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false)
  }, [])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setError(null) }
  }

  // Image and video have different creative formats; switching media type
  // resets the format to a valid default for the new list.
  const formats = mediaType === 'image' ? IMAGE_FORMATS : VIDEO_FORMATS
  const changeMediaType = useCallback((next: 'image' | 'video') => {
    setMediaType(next)
    setFormat(next === 'image' ? IMAGE_FORMATS[0] : VIDEO_FORMATS[0])
  }, [])

  const handleAnalyze = async () => {
    setError(null)

    if (inputMode === 'upload' && !file) { setError('Please select a file to analyze.'); return }
    if (inputMode === 'url' && !mediaUrl.trim()) { setError('Please enter a URL.'); return }

    setIsAnalyzing(true)
    setLoadingStep(0)

    const steps = inputMode === 'url' ? URL_LOADING_STEPS : LOADING_STEPS
    const stepInterval = setInterval(() => {
      setLoadingStep(s => Math.min(s + 1, steps.length - 1))
    }, 4000)

    try {
      let result
      const sharedMeta = { title, description: context, format, role }

      if (inputMode === 'url' && mediaType === 'video') {
        // Social / video URL — send URL string directly to the video-url endpoint
        result = await analyzeVideoUrl(mediaUrl.trim(), sharedMeta)
      } else if (inputMode === 'url') {
        // Direct image URL — proxy-download it then send as a file
        let fetchedFile: File
        try {
          fetchedFile = await fileFromUrl(mediaUrl.trim(), 'image')
        } catch (err) {
          throw new Error(
            `Could not fetch URL: ${err instanceof Error ? err.message : 'unknown error'}`
          )
        }
        result = await analyzeCreative(fetchedFile, { ...sharedMeta, mediaType: 'image' })
      } else {
        // Uploaded file
        result = await analyzeCreative(file!, { ...sharedMeta, mediaType })
      }

      setLastResult(result)
      try { sessionStorage.setItem('f1x8_result', JSON.stringify({ ...result, heatmap: undefined })) } catch {}
      router.push('/results')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.')
      setIsAnalyzing(false)
    } finally {
      clearInterval(stepInterval)
    }
  }

  const source = inputMode === 'upload' ? (file ? 'FILE' : '—') : 'URL'
  const configReadout = `${mediaType === 'image' ? 'IMG' : 'VID'} · ${source} · ${role.toUpperCase()} · ${format}`

  return (
    <main className="relative min-h-screen bg-noir text-[#fafafa]">
      <Nav active="upload" />
      <div className="absolute inset-0 bg-grid pointer-events-none" aria-hidden="true" />
      <div className="absolute inset-0 spotlight pointer-events-none" aria-hidden="true" />

      <div className="relative pt-16 min-h-screen flex items-start justify-center px-4 sm:px-6 py-16">
        <div className="w-full max-w-2xl">

          {/* Header — centered */}
          <div className="text-center mb-10 animate-rise">
            <div className="inline-flex items-center gap-2.5 mb-6 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.03]">
              <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" aria-hidden="true" />
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/55">
                {isAnalyzing ? 'Analyzing' : 'Engine ready'}
              </span>
            </div>
            <h1 className="font-mono font-semibold tracking-tightest text-[#fafafa] leading-tight"
                style={{ fontSize: 'clamp(1.75rem, 4vw, 2.75rem)' }}>
              Run a diagnostic
              <span className="text-accent cursor-blink">_</span>
            </h1>
            <p className="font-sans text-sm text-white/50 mt-3 max-w-md mx-auto">
              Drop a video or static image. Full attention diagnosis in under thirty seconds.
            </p>
          </div>

          {/* Console panel */}
          <div className="rounded-[5px] border border-white/10 bg-panel overflow-hidden animate-rise"
               style={{ animationDelay: '0.1s' }}>

            {/* Window-chrome header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-white/[0.02]">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full border border-white/15" aria-hidden="true" />
                <span className="w-2.5 h-2.5 rounded-full border border-white/15" aria-hidden="true" />
                <span className="w-2.5 h-2.5 rounded-full bg-accent/80" aria-hidden="true" />
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40 ml-2">
                  F1X8 // diagnostic engine
                </span>
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/30">
                v2.1
              </span>
            </div>

            <div className="p-5 sm:p-7 space-y-7">

              {/* Step 01 — Medium + Source */}
              <Field step="01" label="Input">
                <div className="grid grid-cols-2 gap-3">
                  <Segment
                    options={[['image', 'Static'], ['video', 'Video']]}
                    value={mediaType}
                    onChange={v => changeMediaType(v as 'image' | 'video')}
                    disabled={isAnalyzing}
                  />
                  <Segment
                    options={[['upload', 'Upload'], ['url', 'URL']]}
                    value={inputMode}
                    onChange={v => { setInputMode(v as InputMode); setError(null) }}
                    disabled={isAnalyzing}
                  />
                </div>
              </Field>

              {/* Step 02 — Source target */}
              <Field step="02" label="Creative">
                {inputMode === 'upload' ? (
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => !isAnalyzing && fileInputRef.current?.click()}
                    onKeyDown={e => { if (!isAnalyzing && (e.key === 'Enter' || e.key === ' ')) fileInputRef.current?.click() }}
                    role="button"
                    tabIndex={0}
                    aria-label="Upload creative file"
                    className={`group relative w-full h-52 flex flex-col items-center justify-center rounded-[3px] border transition-all duration-300 select-none
                      ${isAnalyzing ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                      ${isDragging ? 'border-accent bg-accent/5'
                        : file ? 'border-white/25 bg-white/[0.02]'
                        : 'border-dashed border-white/15 bg-white/[0.015] hover:border-white/30'}`}
                  >
                    {/* crosshair corner ticks */}
                    <CornerTicks active={isDragging} />
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="sr-only"
                      accept={mediaType === 'image' ? 'image/jpeg,image/png,image/webp' : 'video/mp4,video/quicktime'}
                      onChange={handleFileInput}
                      aria-hidden="true"
                      tabIndex={-1}
                      disabled={isAnalyzing}
                    />
                    {file ? (
                      <div className="flex flex-col items-center gap-2 px-6 w-full">
                        <FileIcon />
                        <p className="font-mono text-sm text-accent truncate max-w-xs">{file.name}</p>
                        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/40">
                          {(file.size / 1024 / 1024).toFixed(1)} MB · click to replace
                        </p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-3">
                        <UploadIcon dragging={isDragging} />
                        <p className="font-sans text-sm text-white/60 mt-1">
                          {isDragging ? 'Release to upload' : 'Drop file here, or click to browse'}
                        </p>
                        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/35">
                          {mediaType === 'image' ? 'JPG · PNG · WebP' : 'MP4 · MOV'}&ensp;·&ensp;max 50 MB
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center gap-2 rounded-[3px] border border-white/15 bg-white/[0.02] px-3 focus-within:border-accent transition-colors duration-300">
                      <span className="font-mono text-xs text-accent/70 select-none">›</span>
                      <input
                        type="url"
                        value={mediaUrl}
                        onChange={e => {
                          const val = e.target.value
                          setMediaUrl(val)
                          setError(null)
                          // Auto-switch to video for social media links
                          if (/tiktok\.com|instagram\.com|youtube\.com|youtu\.be|twitter\.com|x\.com|facebook\.com/.test(val)) {
                            changeMediaType('video')
                          }
                        }}
                        placeholder="https://tiktok.com/…  or direct image/video URL"
                        disabled={isAnalyzing}
                        className="flex-1 bg-transparent py-3.5 font-mono text-xs text-[#fafafa] placeholder-white/30 focus:outline-none disabled:opacity-50"
                      />
                    </div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/35 mt-2.5">
                      TikTok · Instagram · YouTube · or direct media URL
                    </p>
                  </div>
                )}
              </Field>

              {/* Step 03 — Lens */}
              <Field step="03" label="Read as">
                <Segment
                  options={ROLES.map(r => [r, r] as [string, string])}
                  value={role}
                  onChange={v => setRole(v as Role)}
                  disabled={isAnalyzing}
                  small
                />
              </Field>

              {/* Step 04 — Parameters */}
              <Field step="04" label="Parameters">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="relative">
                    <select
                      value={format}
                      onChange={e => setFormat(e.target.value as Format)}
                      disabled={isAnalyzing}
                      aria-label="Format"
                      className="w-full appearance-none bg-white/[0.02] border border-white/15 rounded-[3px] px-3.5 py-3 font-mono text-xs text-[#fafafa] focus:outline-none focus:border-accent cursor-pointer transition-colors duration-300 pr-8 disabled:opacity-50"
                    >
                      {formats.map(f => <option key={f} value={f} className="bg-panel">{f}</option>)}
                    </select>
                    <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-white/40">
                      <ChevronIcon />
                    </div>
                  </div>
                  <input
                    type="text"
                    value={title}
                    onChange={e => setTitle(e.target.value)}
                    placeholder="Title (optional)"
                    disabled={isAnalyzing}
                    className="w-full bg-white/[0.02] border border-white/15 rounded-[3px] px-3.5 py-3 font-mono text-xs text-[#fafafa] placeholder-white/30 focus:outline-none focus:border-accent transition-colors duration-300 disabled:opacity-50"
                  />
                </div>
                <textarea
                  value={context}
                  onChange={e => setContext(e.target.value)}
                  placeholder="Context — campaign objective, audience, anything the diagnostic should account for… (optional)"
                  rows={2}
                  disabled={isAnalyzing}
                  className="w-full mt-3 bg-white/[0.02] border border-white/15 rounded-[3px] px-3.5 py-3 font-sans text-xs text-[#fafafa] placeholder-white/30 focus:outline-none focus:border-accent transition-colors duration-300 resize-none disabled:opacity-50"
                />
              </Field>

              {/* Error */}
              {error && (
                <div className="flex items-start gap-2 px-4 py-3 border border-accent/40 bg-accent/10 rounded-[3px]">
                  <span className="font-mono text-xs text-accent">✕</span>
                  <p className="font-mono text-xs text-accent leading-relaxed">{error}</p>
                </div>
              )}

              {/* Analyze button */}
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="group w-full bg-accent text-[#0a0a0a] font-mono text-[11px] font-medium uppercase tracking-[0.18em] py-4 rounded-[3px]
                           hover:bg-[#ff6a44]
                           disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:bg-accent
                           transition-colors duration-300 ease-cinematic
                           flex items-center justify-center gap-3
                           shadow-[0_0_36px_-10px_rgba(255,79,35,0.7)]"
              >
                {isAnalyzing ? (
                  <>
                    <SpinnerIcon />
                    {(inputMode === 'url' ? URL_LOADING_STEPS : LOADING_STEPS)[loadingStep]}
                  </>
                ) : (
                  <>
                    Execute analysis
                    <ArrowIcon />
                  </>
                )}
              </button>
            </div>

            {/* Console status line */}
            <div className="flex items-center justify-between px-5 py-2.5 border-t border-white/10 bg-white/[0.02]">
              <span className="font-mono text-[10px] tracking-[0.14em] text-white/35">
                <span className="text-accent/70">cfg</span> {configReadout}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/30">
                {isAnalyzing ? 'processing…' : 'idle'}
              </span>
            </div>
          </div>

          {isAnalyzing && (
            <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/35 text-center mt-4">
              This may take up to a few minutes for large files.
            </p>
          )}
        </div>
      </div>
    </main>
  )
}

/* ── Building blocks ────────────────────────────────────────────────────────── */

function Field({ step, label, children }: { step: string; label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2.5 mb-3">
        <span className="font-mono text-[10px] text-accent/70 tracking-[0.1em]">{step}</span>
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/45">{label}</span>
        <span className="h-px flex-1 bg-white/10" aria-hidden="true" />
      </div>
      {children}
    </div>
  )
}

function Segment({
  options, value, onChange, disabled, small,
}: {
  options: [string, string][]
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  small?: boolean
}) {
  return (
    <div className="flex rounded-[3px] overflow-hidden border border-white/15">
      {options.map(([val, label]) => (
        <button
          key={val}
          onClick={() => onChange(val)}
          aria-pressed={value === val}
          disabled={disabled}
          className={`flex-1 ${small ? 'py-2.5 px-1.5 text-[10px]' : 'py-3 text-[11px]'} font-mono uppercase tracking-[0.12em] leading-tight transition-colors duration-300 disabled:opacity-50
            ${value === val ? 'bg-accent text-[#0a0a0a]' : 'bg-transparent text-white/45 hover:text-white/80 hover:bg-white/[0.03]'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

/* ── Icons ──────────────────────────────────────────────────────────────────── */

function CornerTicks({ active }: { active: boolean }) {
  const c = active ? 'border-accent' : 'border-white/20'
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-2.5 transition-colors duration-300">
      <span className={`absolute top-0 left-0 w-3 h-3 border-t border-l ${c}`} />
      <span className={`absolute top-0 right-0 w-3 h-3 border-t border-r ${c}`} />
      <span className={`absolute bottom-0 left-0 w-3 h-3 border-b border-l ${c}`} />
      <span className={`absolute bottom-0 right-0 w-3 h-3 border-b border-r ${c}`} />
    </div>
  )
}

function UploadIcon({ dragging }: { dragging: boolean }) {
  return (
    <svg width="30" height="30" viewBox="0 0 28 28" fill="none" aria-hidden="true"
      className={`transition-colors duration-300 ${dragging ? 'text-accent' : 'text-white/40'}`}>
      <path d="M14 18V8M9 13l5-5 5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 21h18" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="text-accent">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M14 2v6h6M8 13h8M8 17h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg width="15" height="11" viewBox="0 0 16 12" fill="none" aria-hidden="true"
      className="transition-transform duration-300 ease-cinematic group-hover:translate-x-1">
      <path d="M1 6h13M10 1l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true" className="animate-spin">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
        strokeDasharray="28" strokeDashoffset="10" />
    </svg>
  )
}
