import { NextRequest, NextResponse } from 'next/server'
import { buildAdaptPrompt } from '@/lib/adaptPrompt'

// Vercel Hobby plan caps serverless at 300s
export const maxDuration = 300
export const dynamic = 'force-dynamic'

const HF_BASE = 'https://platform.higgsfield.ai'
// Popcorn is Higgsfield's reference-driven image-edit model on the platform API.
const HF_MODEL = '/higgsfield-ai/popcorn/auto'
const POPCORN_RATIOS = ['3:4', '2:3', '3:2', '9:16', '1:1', '4:3', '16:9']

function hfAuth(): string {
  const id = process.env.HF_API_KEY_ID
  const secret = process.env.HF_API_KEY_SECRET
  if (!id || !secret) throw new Error('Higgsfield API keys not configured (HF_API_KEY_ID / HF_API_KEY_SECRET)')
  return `Key ${id}:${secret}`
}

// Minimal PNG/JPEG dimension readers so the output matches the source KV's ratio.
function imageDimensions(buf: Buffer): { width: number; height: number } | null {
  if (buf.length > 24 && buf.readUInt32BE(0) === 0x89504e47) {
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) }
  }
  if (buf.length > 4 && buf.readUInt16BE(0) === 0xffd8) {
    let off = 2
    while (off + 9 < buf.length) {
      if (buf[off] !== 0xff) break
      const marker = buf[off + 1]
      const size = buf.readUInt16BE(off + 2)
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { height: buf.readUInt16BE(off + 5), width: buf.readUInt16BE(off + 7) }
      }
      off += 2 + size
    }
  }
  return null
}

function closestRatio(width: number, height: number): string {
  const target = width / height
  let best = '1:1'
  let bestDiff = Infinity
  for (const r of POPCORN_RATIOS) {
    const [w, h] = r.split(':').map(Number)
    const diff = Math.abs(w / h - target)
    if (diff < bestDiff) { bestDiff = diff; best = r }
  }
  return best
}

export async function POST(req: NextRequest) {
  try {
    const auth = hfAuth()
    const body = await req.json()
    const { image, risks, strengths, extra } = body || {}
    if (typeof image !== 'string' || !image.startsWith('data:')) {
      return NextResponse.json({ error: 'image must be a data URL' }, { status: 400 })
    }
    const { prompt, applied } = buildAdaptPrompt(risks || [], strengths || [], extra)

    const [, mime, b64] = image.match(/^data:([^;]+);base64,(.*)$/s) || []
    if (!mime || !b64) return NextResponse.json({ error: 'unsupported image data URL' }, { status: 400 })
    const bytes = Buffer.from(b64, 'base64')
    const dims = imageDimensions(bytes)
    const aspectRatio = dims ? closestRatio(dims.width, dims.height) : '1:1'

    // 1) presigned upload so the generation request can reference a public URL
    const uploadRes = await fetch(`${HF_BASE}/files/generate-upload-url`, {
      method: 'POST',
      headers: { Authorization: auth, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content_type: mime }),
    })
    if (!uploadRes.ok) {
      return NextResponse.json({ error: `upload-url failed (${uploadRes.status})` }, { status: 502 })
    }
    const { public_url, upload_url, upload_headers } = await uploadRes.json()
    const putRes = await fetch(upload_url, {
      method: 'PUT',
      // the presigned signature covers these headers (Content-Type, x-amz-tagging)
      headers: upload_headers || { 'Content-Type': mime },
      body: new Uint8Array(bytes),
    })
    if (!putRes.ok) {
      return NextResponse.json({ error: `image upload failed (${putRes.status})` }, { status: 502 })
    }

    // 2) submit the edit
    const genRes = await fetch(`${HF_BASE}${HF_MODEL}`, {
      method: 'POST',
      headers: { Authorization: auth, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        image_urls: [public_url],
        aspect_ratio: aspectRatio,
        resolution: '1600p',
      }),
    })
    const gen = await genRes.json().catch(() => ({}))
    if (!genRes.ok) {
      return NextResponse.json(
        { error: `generation submit failed (${genRes.status}): ${JSON.stringify(gen).slice(0, 300)}` },
        { status: 502 },
      )
    }
    return NextResponse.json({
      request_id: gen.request_id,
      prompt,
      applied_count: applied.length,
      aspect_ratio: aspectRatio,
    })
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'adapt failed' }, { status: 500 })
  }
}

export async function GET(req: NextRequest) {
  try {
    // Proxy a completed result image (the CDN has no CORS headers, and the
    // rescore flow needs the bytes client-side).
    const download = req.nextUrl.searchParams.get('download')
    if (download) {
      const url = new URL(download)
      if (url.protocol !== 'https:' || !url.hostname.endsWith('.cloudfront.net')) {
        return NextResponse.json({ error: 'download host not allowed' }, { status: 400 })
      }
      const res = await fetch(url)
      if (!res.ok) return NextResponse.json({ error: `download failed (${res.status})` }, { status: 502 })
      return new NextResponse(res.body, {
        headers: { 'Content-Type': res.headers.get('content-type') || 'image/png' },
      })
    }

    const requestId = req.nextUrl.searchParams.get('request_id')
    if (!requestId || !/^[a-z0-9-]+$/i.test(requestId)) {
      return NextResponse.json({ error: 'request_id required' }, { status: 400 })
    }
    const res = await fetch(`${HF_BASE}/requests/${requestId}/status`, {
      headers: { Authorization: hfAuth() },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      return NextResponse.json({ error: `status failed (${res.status})` }, { status: 502 })
    }
    // Normalize: images may be [{url}] or [url]
    const images = (data.images || [])
      .map((im: any) => (typeof im === 'string' ? im : im?.url))
      .filter(Boolean)
    return NextResponse.json({ status: data.status, images, error: data.error })
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'status failed' }, { status: 500 })
  }
}
