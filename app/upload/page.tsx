'use client'
import { useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Nav from '@/components/Nav'
import { analyzeCreative, analyzeVideoUrl } from '@/lib/api'
import { setLastResult } from '@/lib/resultStore'

const ROLES = ['Creative Director', 'Marketer', 'Strategist', 'Executive'] as const
const FORMATS = ['KV', 'OOH', 'Banner', 'Print', 'Social'] as const
type Role = typeof ROLES[number]
type Format = typeof FORMATS[number]
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

  return (
    <main className="bg-paper text-ink min-h-screen bg-grid-light">
      <Nav active="upload" theme="light" />

      <div className="pt-16 min-h-screen flex items-start justify-center px-6 py-20">
        <div className="w-full max-w-2xl">

          {/* Header */}
          <div className="mb-12 animate-rise">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent mb-5">
              New Diagnostic
            </p>
            <h1 className="font-serif font-normal tracking-tightest text-ink leading-[1.05] mb-4"
                style={{ fontSize: 'clamp(2.25rem, 5vw, 3.5rem)' }}>
              Upload your creative.
            </h1>
            <p className="prose-serif text-lg text-ink/55 max-w-md">
              Drop a video or static image. Full diagnosis in under thirty seconds.
            </p>
          </div>

          {/* Media type toggle */}
          <SegmentLabel>Medium</SegmentLabel>
          <div className="flex mb-6 rounded-[2px] overflow-hidden border border-ink/15">
            {(['image', 'video'] as const).map(type => (
              <button
                key={type}
                onClick={() => setMediaType(type)}
                aria-pressed={mediaType === type}
                className={`flex-1 py-3 text-[10px] font-mono uppercase tracking-[0.18em] transition-colors duration-300
                  ${mediaType === type ? 'bg-ink text-paper' : 'bg-transparent text-ink/50 hover:text-ink'}`}
              >
                {type === 'image' ? 'Static image' : 'Video'}
              </button>
            ))}
          </div>

          {/* Input mode toggle */}
          <SegmentLabel>Source</SegmentLabel>
          <div className="flex mb-8 rounded-[2px] overflow-hidden border border-ink/15">
            {(['upload', 'url'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => { setInputMode(mode); setError(null) }}
                aria-pressed={inputMode === mode}
                disabled={isAnalyzing}
                className={`flex-1 py-3 text-[10px] font-mono uppercase tracking-[0.18em] transition-colors duration-300 disabled:opacity-50
                  ${inputMode === mode ? 'bg-ink text-paper' : 'bg-transparent text-ink/50 hover:text-ink'}`}
              >
                {mode === 'upload' ? 'Upload file' : 'Paste URL'}
              </button>
            ))}
          </div>

          {/* Drop zone / URL input */}
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
              className={`relative w-full h-56 flex flex-col items-center justify-center rounded-[2px] border border-dashed transition-all duration-300 mb-8 select-none
                ${isAnalyzing ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                ${isDragging ? 'border-accent bg-accent/5'
                  : file ? 'border-ink/40 bg-white/40'
                  : 'border-ink/20 bg-white/30 hover:border-ink/40'}`}
            >
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
                  <p className="font-mono text-sm text-ink truncate max-w-xs">{file.name}</p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/45">
                    {(file.size / 1024 / 1024).toFixed(1)} MB · click to replace
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <UploadIcon dragging={isDragging} />
                  <p className="prose-serif text-lg text-ink/70 mt-1">
                    {isDragging ? 'Release to upload' : 'Drop file here, or click to browse'}
                  </p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/40">
                    {mediaType === 'image' ? 'JPG · PNG · WebP' : 'MP4 · MOV'}&ensp;·&ensp;max 50 MB
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="mb-8">
              <input
                type="url"
                value={mediaUrl}
                onChange={e => {
                  const val = e.target.value
                  setMediaUrl(val)
                  setError(null)
                  // Auto-switch to video for social media links
                  if (/tiktok\.com|instagram\.com|youtube\.com|youtu\.be|twitter\.com|x\.com|facebook\.com/.test(val)) {
                    setMediaType('video')
                  }
                }}
                placeholder="https://www.tiktok.com/… or direct image/video URL"
                disabled={isAnalyzing}
                className="w-full bg-white/40 border border-ink/15 rounded-[2px] px-4 py-3.5 font-mono text-xs text-ink placeholder-ink/35 focus:outline-none focus:border-accent transition-colors duration-300 disabled:opacity-50"
              />
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/40 mt-3">
                TikTok · Instagram · YouTube · or direct image / video URL
              </p>
            </div>
          )}

          {/* Role selector */}
          <div className="mb-6">
            <SegmentLabel>Read as</SegmentLabel>
            <div className="flex rounded-[2px] overflow-hidden border border-ink/15">
              {ROLES.map(r => (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  aria-pressed={role === r}
                  disabled={isAnalyzing}
                  className={`flex-1 py-3 px-2 text-[11px] font-mono leading-tight transition-colors duration-300
                    ${role === r ? 'bg-ink text-paper' : 'bg-transparent text-ink/50 hover:text-ink'}`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Format + Title */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-5">
            <div>
              <SegmentLabel>Format</SegmentLabel>
              <div className="relative">
                <select
                  value={format}
                  onChange={e => setFormat(e.target.value as Format)}
                  disabled={isAnalyzing}
                  className="w-full appearance-none bg-white/40 border border-ink/15 rounded-[2px] px-4 py-3 font-mono text-xs text-ink focus:outline-none focus:border-accent cursor-pointer transition-colors duration-300 pr-8 disabled:opacity-50"
                >
                  {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
                <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink/45">
                  <ChevronIcon />
                </div>
              </div>
            </div>

            <div>
              <SegmentLabel>
                Title <span className="text-ink/30">(optional)</span>
              </SegmentLabel>
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Ramadan KV — Hero Banner"
                disabled={isAnalyzing}
                className="w-full bg-white/40 border border-ink/15 rounded-[2px] px-4 py-3 font-mono text-xs text-ink placeholder-ink/35 focus:outline-none focus:border-accent transition-colors duration-300 disabled:opacity-50"
              />
            </div>
          </div>

          {/* Context */}
          <div className="mb-8">
            <SegmentLabel>
              Context <span className="text-ink/30">(optional)</span>
            </SegmentLabel>
            <textarea
              value={context}
              onChange={e => setContext(e.target.value)}
              placeholder="Campaign objective, target audience, or anything the diagnostic should account for…"
              rows={3}
              disabled={isAnalyzing}
              className="w-full bg-white/40 border border-ink/15 rounded-[2px] px-4 py-3 font-mono text-xs text-ink placeholder-ink/35 focus:outline-none focus:border-accent transition-colors duration-300 resize-none disabled:opacity-50"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="mb-5 px-4 py-3 border border-accent/40 bg-accent/10 rounded-[2px]">
              <p className="font-mono text-xs text-accent">{error}</p>
            </div>
          )}

          {/* Analyze button */}
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="group w-full bg-ink text-paper font-mono text-[11px] uppercase tracking-[0.18em] py-4 rounded-[2px]
                       hover:bg-accent
                       disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:bg-ink
                       transition-colors duration-300 ease-cinematic
                       flex items-center justify-center gap-3"
          >
            {isAnalyzing ? (
              <>
                <SpinnerIcon />
                {(inputMode === 'url' ? URL_LOADING_STEPS : LOADING_STEPS)[loadingStep]}
              </>
            ) : (
              <>
                Analyze creative
                <ArrowIcon />
              </>
            )}
          </button>

          {isAnalyzing && (
            <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/40 text-center mt-4">
              This may take up to a few minutes for large files.
            </p>
          )}
        </div>
      </div>
    </main>
  )
}

/* ── Small building blocks ──────────────────────────────────────────────────── */

function SegmentLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/45 mb-2.5">
      {children}
    </p>
  )
}

/* ── Icons ──────────────────────────────────────────────────────────────────── */

function UploadIcon({ dragging }: { dragging: boolean }) {
  return (
    <svg width="30" height="30" viewBox="0 0 28 28" fill="none" aria-hidden="true"
      className={`transition-colors duration-300 ${dragging ? 'text-accent' : 'text-ink/40'}`}>
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
      <path d="M1 6h13M10 1l5 5-5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
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
