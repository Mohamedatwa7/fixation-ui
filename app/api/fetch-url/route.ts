import { NextRequest, NextResponse } from 'next/server'
import { execFile } from 'child_process'
import { promisify } from 'util'
import { readFile, unlink } from 'fs/promises'
import { tmpdir } from 'os'
import { join } from 'path'
import { randomBytes } from 'crypto'

const execFileAsync = promisify(execFile)
const YT_DLP = '/Users/yasminatwa/Library/Python/3.9/bin/yt-dlp'

export async function POST(req: NextRequest) {
  let url: string
  try {
    const body = await req.json()
    url = body.url
    new URL(url)
  } catch {
    return NextResponse.json({ error: 'Invalid URL' }, { status: 400 })
  }

  try {
    if (/tiktok\.com/.test(url)) {
      return await handleTikTok(url)
    }
    if (/instagram\.com|youtube\.com|youtu\.be|twitter\.com|x\.com|facebook\.com/.test(url)) {
      return await handleYtDlp(url)
    }
    return await handleDirectUrl(url)
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to fetch URL' },
      { status: 502 },
    )
  }
}

// Strip tracking query params — they confuse TikTok download APIs
function cleanTikTokUrl(url: string): string {
  try {
    const u = new URL(url)
    return `${u.origin}${u.pathname}`
  } catch {
    return url
  }
}

async function fetchVideoUrl(videoUrl: string): Promise<ArrayBuffer | null> {
  try {
    const res = await fetch(videoUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; F1X8/1.0)' },
    })
    if (res.ok) return await res.arrayBuffer()
  } catch {}
  return null
}

async function handleTikTok(url: string): Promise<NextResponse> {
  const clean = cleanTikTokUrl(url)

  // API 1: tikwm
  try {
    const api = await fetch(`https://www.tikwm.com/api/?url=${encodeURIComponent(clean)}`, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; F1X8/1.0)' },
    })
    const text = await api.text()
    const json = JSON.parse(text)
    const videoUrl = json.data?.play
    if (json.code === 0 && videoUrl) {
      const buf = await fetchVideoUrl(videoUrl)
      if (buf) return new NextResponse(buf, { headers: { 'Content-Type': 'video/mp4' } })
    }
  } catch {}

  // API 2: tikmate
  try {
    const api = await fetch(`https://api.tikmate.app/api/lookup?url=${encodeURIComponent(clean)}`, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; F1X8/1.0)' },
    })
    const text = await api.text()
    const json = JSON.parse(text)
    const videoUrl = json.url || json.data?.url
    if (videoUrl) {
      const buf = await fetchVideoUrl(videoUrl)
      if (buf) return new NextResponse(buf, { headers: { 'Content-Type': 'video/mp4' } })
    }
  } catch {}

  throw new Error('Could not download TikTok video. The video may be private or all download services are temporarily unavailable.')
}

async function handleYtDlp(url: string): Promise<NextResponse> {
  const id = randomBytes(8).toString('hex')
  const outPath = join(tmpdir(), `f1x8-${id}.mp4`)
  try {
    await execFileAsync(YT_DLP, [
      '--no-playlist',
      '--max-filesize', '200m',
      '-f', 'mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
      '--merge-output-format', 'mp4',
      '-o', outPath,
      url,
    ], { timeout: 120_000 })
    const buffer = await readFile(outPath)
    return new NextResponse(buffer, { headers: { 'Content-Type': 'video/mp4' } })
  } finally {
    unlink(outPath).catch(() => {})
  }
}

async function handleDirectUrl(url: string): Promise<NextResponse> {
  const upstream = await fetch(url, {
    redirect: 'follow',
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; F1X8/1.0)',
      'Accept': 'image/*,video/*,*/*',
    },
  })
  if (!upstream.ok) {
    throw new Error(`Could not fetch URL (${upstream.status})`)
  }
  const buffer = await upstream.arrayBuffer()
  const contentType = upstream.headers.get('content-type') ?? 'application/octet-stream'
  return new NextResponse(buffer, { headers: { 'Content-Type': contentType } })
}
