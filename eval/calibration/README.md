# F1X8 calibration study (step 1)

Correlates the deployed **Engagement Potential** score with **realized organic
engagement** on @samsunggulf creatives scraped by the SamsungSentiment Apify
pipeline. Answers: *does the judge track reality at all, and which KPIs carry
the signal?* — before investing in prompt anchors (step 2) or a Qwen LoRA
ranker (step 3).

## Setup

Create `eval/calibration/.env` (gitignored):

```
SUPABASE_URL=https://<samsungsentiment-project>.supabase.co
SUPABASE_KEY=<anon key — RLS allows public read on social_posts>
F1X8_API_URL=<https://...modal.run  or the deployed vercel.app site>
```

Both values are in the SamsungSentiment Vercel project env
(`NEXT_PUBLIC_SUPABASE_URL` / anon key); `F1X8_API_URL` is fixation-ui's
`NEXT_PUBLIC_API_URL` on Vercel. `pip install requests` if missing.

## Run

```sh
python eval/calibration/calibrate.py all      # or step-by-step:
python eval/calibration/calibrate.py export   # Supabase -> data/posts.json
python eval/calibration/calibrate.py build    # cohort percentiles + stratified sample
python eval/calibration/calibrate.py download # media (reports expired-CDN coverage)
python eval/calibration/calibrate.py run      # scores via deployed API (resumable)
python eval/calibration/calibrate.py report   # data/REPORT.md
```

`run` is the paid step: ~60 image creatives through the full pipeline
(A10G + one live Opus judge call each) ≈ **$2–4 and 15–25 min** at 3-way
concurrency. `SAMPLE_CAP` env overrides the 60 default. Already-scored
creatives are skipped on re-run.

## Method

- **Label** = engagement percentile within cohort (platform × media-kind ×
  metric-basis × quarter; quarters merged when n < 8). Per-view rate for
  videos with ≥100 views, raw likes+comments+shares otherwise — single brand
  account, so audience is constant within a cohort.
- **Excluded**: contest/giveaway posts (mechanic-driven engagement), Unpacked
  event posts (news-driven), zero-across-the-board rows (scrape gaps).
- **Sample** = top + bottom quartile images, most extreme first, balanced
  across platform × stratum. Extremes make the discrimination question sharp
  with a small paid sample.
- **Headline metric** = top-vs-bottom **AUC** (Spearman is also reported but
  is inflated by the stratified design — see report caveats).

## Reading the result

- **AUC ≥ ~0.65** — the judge sees something real; steps 2/3 are worth it,
  and the per-KPI table shows which KPIs to anchor.
- **AUC ~0.5** — score is engagement-blind on this distribution; fix the
  prompt/measured features before any fine-tuning.
- **AUC < ~0.4** — score is *anti*-correlated; check funnel misclassification
  first (a stage flip changes KPI weighting).

The scored images in `data/media/` double as real Samsung-category KVs for
`eval/assets/` (the reliability harness currently runs on synthetic samples).
