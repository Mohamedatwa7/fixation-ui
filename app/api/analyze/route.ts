import { NextRequest, NextResponse } from 'next/server'

// Vercel Hobby plan caps serverless functions at 300s (Pro allows more).
export const maxDuration = 300
export const dynamic = 'force-dynamic'

// Deployed Modal backend — used when NEXT_PUBLIC_API_URL is not set so a
// missing/clobbered .env.local doesn't silently break every diagnostic.
const DEFAULT_API_URL = 'https://mohamedymay7--fixation-api-fastapi-app.modal.run'

export async function POST(req: NextRequest) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL
  if (!apiUrl) {
    return NextResponse.json({ error: 'API URL not configured' }, { status: 503 })
  }

  const endpoint = req.nextUrl.searchParams.get('endpoint') ?? '/api/analyze/image'

  try {
    const form = await req.formData()
    
    const upstream = await fetch(`${apiUrl}${endpoint}`, {
      method: 'POST',
      body: form,
    })

    const text = await upstream.text()
    let data: unknown
    try {
      data = JSON.parse(text)
    } catch {
      return NextResponse.json(
        { error: `Backend error (${upstream.status})` },
        { status: upstream.status },
      )
    }
    return NextResponse.json(data, { status: upstream.status })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Upstream request failed' },
      { status: 502 },
    )
  }
}

export async function GET(req: NextRequest) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL
  if (!apiUrl) {
    return NextResponse.json({ error: 'API URL not configured' }, { status: 503 })
  }

  const endpoint = req.nextUrl.searchParams.get('endpoint') ?? '/api/job/default'

  try {
    const upstream = await fetch(`${apiUrl}${endpoint}`, {
      method: 'GET',
    })

    const text = await upstream.text()
    let data: unknown
    try {
      data = JSON.parse(text)
    } catch {
      return NextResponse.json(
        { error: `Backend error (${upstream.status})` },
        { status: upstream.status },
      )
    }
    return NextResponse.json(data, { status: upstream.status })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Upstream request failed' },
      { status: 502 },
    )
  }
}
