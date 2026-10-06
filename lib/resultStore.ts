let lastResult: any = null
let lastImage: { b64: string; mediaType: string } | null = null

export function setLastResult(r: any) {
  lastResult = r
}

export function getLastResult() {
  return lastResult
}

/** Original creative (base64, no data-URL prefix) kept for business Q&A. */
export function setLastImage(b64: string, mediaType: string) {
  lastImage = { b64, mediaType }
}

export function getLastImage() {
  return lastImage
}
