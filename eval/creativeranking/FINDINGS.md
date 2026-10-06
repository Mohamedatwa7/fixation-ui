# CreativeRanking validation findings (2026-10-06)

40,000 creatives scored (AAM saliency + Gini-era design KPIs) against real
CTR outcomes from Alibaba CreativeRanking (1.7M creatives, 215M impressions;
sample: 20k top-quartile-within-product + 20k random, ≥100 shows, ≥3
creatives per product).

## Result: design KPIs carry ZERO outcome signal in this domain

| Test | Result |
|---|---|
| KPI score vs within-product CTR percentile (n=20k) | all five KPIs ±0.02 Spearman, AUC 0.485–0.510 |
| High-CTR winners vs random creatives, distribution AUC (n=40k) | 0.491–0.507 — identical distributions |

Not marginal — flat nulls with tight confidence at this n.

## Why (and why this does NOT kill the Samsung finding)

Taobao product thumbnails are a **range-restricted domain**: nearly every
creative is a clean product shot (sample means: hierarchy 8.7/10,
complexity 9.2/10 — compressed near the ceiling). Within-product variants
differ by crop, background, promo sticker. When craft barely varies,
craft can't explain CTR — clicks ride on price, promo text, product appeal.

The n=132 Samsung calibration result (AAM hierarchy +0.20, contrast +0.15,
hier+contrast composite AUC 0.615) tested *varied brand creatives* against
*organic engagement* — a different regime with real craft variance. It is
weakened as a generalization but not contradicted.

Supporting context: the dataset's own paper (WWW 2021) showed a *learned*
visual model predicts within-product CTR well. Pixels carry the signal;
five global design scalars do not. This validates F1X8's architecture:
the LoRA ranker (learned, outcome-trained) carries prediction; KPIs are
explanatory craft evidence, not outcome predictors.

## Decisions

1. **Do NOT ship benchmark_creativeranking_highctr.json as
   "outcome-calibrated".** Winners occupy no distinctive KPI range here, so
   that claim would be false. The file's distributions are usable only as a
   *descriptive* yardstick ("vs 20k real e-commerce creatives") — honest for
   percentile display (incl. hierarchy_gini), nothing more.
2. **The dataset's real value for F1X8 is ranker pretraining**: ~347k
   eligible creatives in within-product groups with CTR ranks = pairwise
   training data at 2,400x the current 142-image scale, exactly the format
   the LoRA ranker consumes.
3. Keep investing in the judge/ranker for outcome claims; keep KPIs framed
   as craft diagnostics (which the UI already does).

## Artifacts (data/ — gitignored, regenerable via build_benchmark.py)

- sample.json, scores.jsonl (40k), benchmark_creativeranking_highctr.json,
  REPORT.md. Raw dataset at D:\datasets\CreativeRanking (115.6 GB zip +
  extracted 40k sample).
