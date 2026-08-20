// Builds the Higgsfield image-edit prompt from a diagnostic's ranked risks.
// Mirrors scripts/adapt-kv.mjs so the CLI and the web feature produce the
// same recommendation -> revision mapping.
import type { Risk } from './mock-data'

const oneLine = (text: string) => String(text).replace(/\s+/g, ' ').trim()

export function buildAdaptPrompt(
  risks: Risk[],
  strengths: string[],
  extra?: string,
): { prompt: string; applied: Risk[] } {
  const applied = (risks || []).filter(r => oneLine(r.suggested_fix || ''))
  if (applied.length === 0) throw new Error('No suggested fixes to apply')

  const parts: string[] = [
    'Edit this advertising key visual. Apply the following revisions precisely while keeping the product, brand elements, overall layout and style otherwise unchanged.',
  ]
  applied.forEach((r, i) => {
    parts.push(`Revision ${i + 1}: ${oneLine(r.suggested_fix!)}`)
  })
  if (extra) parts.push(`Also: ${oneLine(extra).replace(/([^.!?])$/, '$1.')}`)
  const keep = (strengths || []).slice(0, 4).map(oneLine)
  if (keep.length > 0) parts.push(`Do not degrade what already works: ${keep.join('; ')}.`)
  parts.push(
    'Photorealistic, production-quality advertising finish. Keep all existing text legible and unaltered unless a revision says otherwise.',
  )
  return { prompt: parts.join(' '), applied }
}
