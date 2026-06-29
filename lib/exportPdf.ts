// ─────────────────────────────────────────────────────────────────────────────
// F1X8 — PDF export
// Builds a fully self-contained, print-designed report from a DiagnosticResult
// and opens it in a new window for the browser's native "Save as PDF".
//
// We render a dedicated document (rather than printing the live results DOM) so
// the export ALWAYS contains the complete diagnostic — KPI breakdown, strengths,
// risks and raw JSON — regardless of which panels are collapsed on the page.
// ─────────────────────────────────────────────────────────────────────────────
import type { DiagnosticResult } from './mock-data'
import { scoreColor, scoreLabel } from './score'

const esc = (s: unknown): string =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

function metaRow(result: DiagnosticResult): string {
  const items: { label: string; value: string }[] = [
    { label: 'Role', value: result.role },
    { label: 'Format', value: result.format },
    { label: 'Media', value: result.mediaType },
  ]
  if (result.funnelStage) items.push({ label: 'Funnel', value: `${result.funnelStage} funnel` })
  if (result.productTier) items.push({ label: 'Tier', value: result.productTier })
  items.push({ label: 'Benchmark', value: `Better than ${result.benchmarkPercentile}% of category` })
  return items
    .map(
      i => `<div class="meta-item">
        <span class="meta-label">${esc(i.label)}</span>
        <span class="meta-value">${esc(i.value)}</span>
      </div>`,
    )
    .join('')
}

function kpiRows(result: DiagnosticResult): string {
  return result.kpis
    .map(kpi => {
      const color = scoreColor(kpi.score)
      const pct = Math.max(0, Math.min(100, kpi.score * 10))
      return `<div class="kpi">
        <div class="kpi-head">
          <span class="kpi-label">${esc(kpi.label)}</span>
          <span class="kpi-score" style="color:${color}">${kpi.score.toFixed(1)}${
            kpi.percentile != null ? `<span class="kpi-pct"> · ${kpi.percentile}th pctl</span>` : ''
          }</span>
        </div>
        <div class="bar"><span style="width:${pct}%;background:${color}"></span></div>
        <p class="kpi-method">${esc(kpi.methodology)}</p>
        <p class="kpi-cite">${esc(kpi.citation)}</p>
      </div>`
    })
    .join('')
}

function strengths(result: DiagnosticResult): string {
  if (!result.strengths?.length) return '<li class="empty">None recorded</li>'
  return result.strengths.map(s => `<li><span class="plus">+</span>${esc(s)}</li>`).join('')
}

function risks(result: DiagnosticResult): string {
  if (!result.risks?.length) return '<li class="empty">None recorded</li>'
  return result.risks
    .map(r => {
      const detail = [
        r.evidence && `<span class="risk-sub">Evidence — ${esc(r.evidence)}</span>`,
        r.impact && `<span class="risk-sub">Impact — ${esc(r.impact)}</span>`,
        r.suggested_fix && `<span class="risk-sub">Fix — ${esc(r.suggested_fix)}</span>`,
      ]
        .filter(Boolean)
        .join('')
      return `<li><span class="bang">!</span><span class="risk-body">
        <span class="risk-issue">${esc(r.issue)}${
          r.confidence ? ` <span class="risk-conf">(${esc(r.confidence)} confidence)</span>` : ''
        }</span>${detail}</span></li>`
    })
    .join('')
}

function heatmap(result: DiagnosticResult): string {
  if (result.mediaType === 'video') {
    return `<div class="heatmap-note">Attention heatmap is a video and cannot be embedded in PDF — view it in the live diagnostic.</div>`
  }
  if (result.heatmapDataUrl) {
    return `<img class="heatmap-img" src="${esc(result.heatmapDataUrl)}" alt="Attention heatmap" />`
  }
  return `<div class="heatmap-note">Heatmap not available for this result.</div>`
}

export function buildReportHtml(result: DiagnosticResult): string {
  const score = result.score ?? 0
  const color = scoreColor(score)
  const generated = new Date().toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>F1X8 Diagnostic — ${esc(result.title || result.id)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
<style>
  :root {
    --paper:#f3f0ea; --ink:#100f0c; --accent:#ff4f23;
    --line:rgba(16,15,12,0.14); --soft:rgba(16,15,12,0.55);
  }
  * { box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  html,body { margin:0; padding:0; background:var(--paper); color:var(--ink); }
  body { font-family:'EB Garamond',Georgia,serif; font-size:13px; line-height:1.5; }
  .page { max-width:760px; margin:0 auto; padding:40px 44px 64px; }
  .mono { font-family:'JetBrains Mono',ui-monospace,monospace; }
  .eyebrow { font-family:'JetBrains Mono',monospace; font-size:9px; text-transform:uppercase;
    letter-spacing:0.22em; color:var(--soft); }
  h2.section { font-family:'JetBrains Mono',monospace; font-size:9.5px; text-transform:uppercase;
    letter-spacing:0.22em; color:var(--soft); margin:0 0 14px; font-weight:500; }

  /* Masthead */
  .mast { display:flex; justify-content:space-between; align-items:flex-end;
    border-bottom:1px solid var(--ink); padding-bottom:14px; margin-bottom:28px; }
  .mast .brand { font-family:'JetBrains Mono',monospace; font-weight:500; font-size:13px;
    letter-spacing:0.34em; }
  .mast .sub { font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:0.18em;
    text-transform:uppercase; color:var(--soft); margin-top:4px; }
  .mast .when { font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:0.14em;
    color:var(--soft); text-align:right; }

  /* Verdict */
  .verdict { display:flex; gap:32px; align-items:flex-start; margin-bottom:30px; }
  .score-col { flex:0 0 auto; }
  .score-num { font-family:'JetBrains Mono',monospace; font-weight:500; font-size:78px;
    line-height:0.85; letter-spacing:-0.03em; }
  .score-tag { display:inline-block; font-family:'JetBrains Mono',monospace; font-size:9px;
    text-transform:uppercase; letter-spacing:0.18em; padding:3px 8px; border:1px solid;
    border-radius:2px; margin-top:10px; }
  .verdict-body { flex:1; }
  .verdict-text { font-size:21px; line-height:1.32; font-weight:500; margin:2px 0 16px;
    letter-spacing:-0.01em; }
  .meta { display:flex; flex-wrap:wrap; gap:8px; }
  .meta-item { border:1px solid var(--line); border-radius:2px; padding:4px 9px;
    display:flex; gap:7px; align-items:baseline; }
  .meta-label { font-family:'JetBrains Mono',monospace; font-size:8.5px; text-transform:uppercase;
    letter-spacing:0.16em; color:var(--soft); }
  .meta-value { font-family:'JetBrains Mono',monospace; font-size:9.5px; }

  /* Cards */
  .card { border:1px solid var(--line); border-radius:3px; padding:20px 22px; margin-bottom:18px; }
  .card.accent { border-left:3px solid var(--accent); }
  .fix-issue { font-size:15px; line-height:1.45; margin:0 0 10px; }
  .fix-action { font-size:14px; line-height:1.5; color:#2a2824; margin:0;
    border-top:1px solid var(--line); padding-top:10px; }
  .fix-action b { font-family:'JetBrains Mono',monospace; font-size:9px; text-transform:uppercase;
    letter-spacing:0.18em; color:var(--accent); display:block; margin-bottom:5px; font-weight:500; }

  /* KPI */
  .kpi { margin-bottom:18px; break-inside:avoid; }
  .kpi-head { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px; }
  .kpi-label { font-size:15px; font-weight:500; }
  .kpi-score { font-family:'JetBrains Mono',monospace; font-size:13px; font-weight:500; }
  .kpi-pct { color:var(--soft); font-weight:400; }
  .bar { height:2px; background:var(--line); border-radius:2px; overflow:hidden; margin-bottom:7px; }
  .bar span { display:block; height:100%; }
  .kpi-method { font-size:12.5px; line-height:1.45; color:#3a382f; margin:0 0 3px; }
  .kpi-cite { font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--soft); margin:0; }

  /* Strengths / risks */
  .two-col { display:grid; grid-template-columns:1fr 1fr; gap:0; border:1px solid var(--line);
    border-radius:3px; overflow:hidden; margin-bottom:18px; }
  .two-col > div { padding:20px 22px; }
  .two-col > div:first-child { border-right:1px solid var(--line); }
  ul.list { list-style:none; margin:0; padding:0; }
  ul.list li { display:flex; gap:9px; font-size:13px; line-height:1.45; margin-bottom:10px;
    break-inside:avoid; }
  ul.list li.empty { color:var(--soft); font-style:italic; }
  .plus { color:var(--accent); font-family:monospace; flex:0 0 auto; }
  .bang { color:#c98a1e; font-family:monospace; flex:0 0 auto; }
  .risk-body { display:flex; flex-direction:column; gap:3px; }
  .risk-issue { font-weight:500; }
  .risk-conf { font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--soft);
    text-transform:uppercase; letter-spacing:0.1em; font-weight:400; }
  .risk-sub { font-size:11.5px; color:var(--soft); }

  /* Heatmap */
  .heatmap-img { width:100%; max-height:420px; object-fit:contain; border:1px solid var(--line);
    border-radius:3px; background:#000; }
  .heatmap-note { font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--soft);
    border:1px dashed var(--line); border-radius:3px; padding:18px; text-align:center; }

  /* Raw JSON */
  pre.json { font-family:'JetBrains Mono',monospace; font-size:8.5px; line-height:1.5;
    color:#3a382f; background:#fff; border:1px solid var(--line); border-radius:3px;
    padding:14px; white-space:pre-wrap; word-break:break-word; margin:0; }

  footer { margin-top:32px; padding-top:14px; border-top:1px solid var(--line);
    font-family:'JetBrains Mono',monospace; font-size:8.5px; letter-spacing:0.14em;
    text-transform:uppercase; color:var(--soft); display:flex; justify-content:space-between; }

  .block { margin-bottom:28px; }
  @media print {
    .page { padding:24px 28px; max-width:none; }
    .block, .card, .two-col, .kpi { break-inside:avoid; }
  }
  @page { margin:14mm; }
</style>
</head>
<body>
<div class="page">

  <div class="mast">
    <div>
      <div class="brand">F1X8</div>
      <div class="sub">Creative Engagement Diagnostic</div>
    </div>
    <div class="when">${esc(generated)}<br/>ID · ${esc(result.id)}</div>
  </div>

  ${result.title ? `<div class="eyebrow" style="margin-bottom:18px;">Asset — ${esc(result.title)}</div>` : ''}

  <div class="verdict">
    <div class="score-col">
      <div class="score-num" style="color:${color}">${score.toFixed(1)}</div>
      <span class="score-tag" style="color:${color};border-color:${color}66;background:${color}14">
        ${scoreLabel(score)} · OUT OF 10
      </span>
    </div>
    <div class="verdict-body">
      <p class="verdict-text">${esc(result.verdict)}</p>
      <div class="meta">${metaRow(result)}</div>
    </div>
  </div>

  <div class="block">
    <h2 class="section">Most Important Fix</h2>
    <div class="card accent">
      <p class="fix-issue">${esc(result.fix?.issue)}</p>
      <p class="fix-action"><b>Recommended action</b>${esc(result.fix?.action)}</p>
    </div>
  </div>

  <div class="block">
    <h2 class="section">Attention Heatmap</h2>
    ${heatmap(result)}
  </div>

  <div class="block">
    <h2 class="section">KPI Breakdown</h2>
    ${kpiRows(result)}
  </div>

  <div class="block">
    <h2 class="section">Strengths &amp; Risks</h2>
    <div class="two-col">
      <div>
        <div class="eyebrow" style="margin-bottom:12px;">Strengths</div>
        <ul class="list">${strengths(result)}</ul>
      </div>
      <div>
        <div class="eyebrow" style="margin-bottom:12px;">Risks</div>
        <ul class="list">${risks(result)}</ul>
      </div>
    </div>
  </div>

  <footer>
    <span>F1X8 — Cognitive Creative Diagnostics</span>
    <span>Generated ${esc(generated)}</span>
  </footer>

</div>
</body>
</html>`
}

export function exportResultToPdf(result: DiagnosticResult): void {
  const html = buildReportHtml(result)

  // Render into an off-screen iframe and print that — no popup window (so no
  // popup-blocker fallback to a downloaded .html) and the browser's native
  // "Save as PDF" dialog opens directly over the current page.
  const iframe = document.createElement('iframe')
  iframe.setAttribute('aria-hidden', 'true')
  iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;'
  document.body.appendChild(iframe)

  const doc = iframe.contentWindow?.document
  if (!doc) {
    iframe.remove()
    return
  }
  doc.open()
  doc.write(html)
  doc.close()

  let printed = false
  const triggerPrint = () => {
    if (printed) return
    printed = true
    const win = iframe.contentWindow
    if (win) {
      win.focus()
      win.print()
    }
    // Leave the iframe in place briefly so the print dialog keeps its document.
    setTimeout(() => iframe.remove(), 1000)
  }

  const win = iframe.contentWindow
  if (!win) {
    iframe.remove()
    return
  }
  win.addEventListener('load', () => {
    const fonts = (iframe.contentDocument as Document & { fonts?: FontFaceSet })?.fonts
    if (fonts?.ready) {
      fonts.ready.then(() => setTimeout(triggerPrint, 200))
    }
    setTimeout(triggerPrint, 1200) // fallback if fonts never resolve
  })
}
