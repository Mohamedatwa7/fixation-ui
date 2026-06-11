// Shared score → color/label mapping for the dark "instrument" results UI.
// Luxury-tuned monochrome scale with the accent (#ff4f23) doubling as the
// low-score alert — keeps the palette disciplined.

export const SCORE_HIGH = '#e8e3d6' // warm off-white — confident / good
export const SCORE_MID = '#e0a23c'  // muted gold — review
export const SCORE_LOW = '#ff4f23'  // accent orange-red — alert / fail

export function scoreColor(score: number): string {
  if (score >= 7) return SCORE_HIGH
  if (score >= 4) return SCORE_MID
  return SCORE_LOW
}

export function scoreLabel(score: number): string {
  if (score >= 7) return 'PASS'
  if (score >= 4) return 'REVIEW'
  return 'FAIL'
}
