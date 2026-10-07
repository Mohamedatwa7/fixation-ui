import Nav from '@/components/Nav'

export const metadata = {
  title: 'Methodology — F1X8',
  description:
    'How F1X8 scores are validated: holdout protocol, accuracy numbers, and the honest nulls.',
}

const LEADERBOARD = [
  { scorer: 'F1X8 ranker v2 (Qwen3-VL-4B, outcome-pretrained + fine-tuned)', auc: '0.921', current: true },
  { scorer: 'F1X8 ranker v1 (Qwen2.5-VL-3B, fine-tuned from scratch)', auc: '0.851', current: false },
  { scorer: 'Design-KPI weights, holdout-validated refit', auc: '0.694', current: false },
  { scorer: 'Frontier-LLM judge score (median-of-3 ensemble)', auc: '0.591', current: false },
  { scorer: 'Chance', auc: '0.500', current: false },
]

export default function MethodologyPage() {
  return (
    <main className="min-h-screen bg-noir text-[#fafafa]">
      <Nav />
      <div className="mx-auto max-w-3xl px-6 pt-28 pb-24 space-y-14">
        <header>
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/40 mb-3">
            Methodology
          </p>
          <h1 className="font-mono text-3xl font-semibold tracking-tightest mb-4">
            Numbers we can defend
          </h1>
          <p className="font-sans text-sm text-white/55 leading-relaxed">
            Every accuracy claim on this page comes from creatives the models never
            saw during training, measured against realized market outcomes — not
            panels, not expert opinion, not our own scores grading themselves. We
            publish the misses alongside the hits.
          </p>
        </header>

        <section>
          <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-white/70 mb-4">
            The headline number
          </h2>
          <div className="border border-white/10 bg-panel rounded-[3px] p-6 mb-4">
            <p className="font-mono text-5xl font-semibold tracking-tightest mb-2">92%</p>
            <p className="font-sans text-sm text-white/60 leading-relaxed">
              Shown one creative that genuinely performed well and one that flopped —
              both from a held-out set the model never trained on — F1X8&apos;s ranking
              model identifies the real winner 92 times out of 100 (holdout AUC 0.921,
              top-vs-bottom quartile, n=82 creatives, cohort-normalized organic
              engagement).
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/40 py-2 pr-4">Scorer</th>
                  <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/40 py-2">Holdout AUC</th>
                </tr>
              </thead>
              <tbody>
                {LEADERBOARD.map(row => (
                  <tr key={row.scorer} className="border-b border-white/5">
                    <td className={`font-sans text-xs py-2.5 pr-4 ${row.current ? 'text-white/85' : 'text-white/45'}`}>
                      {row.scorer}{row.current && <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-accent ml-2">live</span>}
                    </td>
                    <td className={`font-mono text-xs py-2.5 ${row.current ? 'text-white/85' : 'text-white/45'}`}>{row.auc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-white/70 mb-4">
            How the validation works
          </h2>
          <ul className="space-y-3 font-sans text-sm text-white/55 leading-relaxed list-none">
            <li><span className="text-white/80">Real outcomes, not opinions.</span> Labels are realized organic engagement on in-market creatives, percentile-ranked within platform, media-kind and quarter cohorts so follower counts and seasonality don&apos;t leak into the target.</li>
            <li><span className="text-white/80">Strict holdout.</span> Evaluation creatives are locked away before training and never touched. Checkpoint selection uses the holdout once; reported numbers come from that same frozen protocol.</li>
            <li><span className="text-white/80">Two-stage training.</span> The ranker is pretrained on 38,500 same-product creative pairs with real impression and click data (215M impressions; Alibaba CreativeRanking, WWW 2021), then fine-tuned on the deployment domain. Pretraining alone reaches 71% pair accuracy on 1,500 unseen products.</li>
            <li><span className="text-white/80">Attention is measured, not guessed.</span> Gaze maps come from a dedicated attention model trained on 1.75M human eye-tracking fixations (AAM, ICML 2026) — because we verified that zero-shot LLM prompting cannot reproduce first-fixation behavior.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-white/70 mb-4">
            The nulls we publish anyway
          </h2>
          <ul className="space-y-3 font-sans text-sm text-white/55 leading-relaxed list-none">
            <li><span className="text-white/80">Hand-crafted design KPIs do not predict clicks in commodity e-commerce.</span> Across 40,000 creatives with real CTR outcomes, all five classical design metrics measured zero (|ρ| ≤ 0.02). That finding is why our outcome prediction is a learned model — and why we present design KPIs as craft diagnostics, never as performance predictors.</li>
            <li><span className="text-white/80">Frontier LLMs are weak outcome predictors.</span> A state-of-the-art LLM judging the same holdout manages 0.591 AUC — barely better than chance. We use LLMs for what they are good at (explanation, diagnosis, simulated audience reads, all labeled as AI judgment) and the trained ranker for prediction.</li>
            <li><span className="text-white/80">Known limits.</span> The 0.921 is domain-specific (one brand&apos;s organic social creatives, n=82 holdout, ±0.05), tested on clear contrasts (top vs bottom quartile), and measures relative ranking — not absolute engagement forecasts, which no one can honestly deliver from a creative alone.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-white/70 mb-4">
            The three-score contract
          </h2>
          <p className="font-sans text-sm text-white/55 leading-relaxed">
            <span className="text-white/80">Engagement Potential</span> is craft judgment —
            it never moves with campaign context. <span className="text-white/80">Organic
            Pull</span> is the calibrated prediction from the validated ranker.{' '}
            <span className="text-white/80">In Context</span> is the expected in-market
            outcome given your declared deployment, and only appears when you supply
            context. Qualitative AI reads (business Q&amp;A, audience panels) are always
            badged as AI judgment, visually separated from grounded measurements, and
            list the evidence they used.
          </p>
        </section>
      </div>
    </main>
  )
}
