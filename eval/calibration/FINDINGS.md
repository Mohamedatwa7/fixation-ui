# Engagement-score calibration & fine-tune findings — 2026-07-28

One-day study: does the deployed Engagement Potential score track realized
organic engagement on @samsunggulf Instagram image creatives, and what is the
best path to making it accurate? All AUCs are top-vs-bottom quartile
discrimination (0.5 = chance) on cohort-normalized engagement percentiles.

## Headline: holdout leaderboard (n=82 unseen creatives)

| scorer | holdout AUC |
|---|---|
| **Qwen2.5-VL-3B LoRA pairwise ranker (trained on 60 images)** | **0.838** |
| Judge KPIs, holdout-validated refit weights | 0.694 |
| Judge brand_strength KPI alone | 0.609 |
| Deployed judge score (median-of-3 ensemble, anchored prompt) | 0.591 |

## What was measured

- **Run 1 (invalid):** expired IG CDN links meant only <1-week-old posts were
  downloadable; immature labels. Fix: `MIN_AGE_DAYS=14` + Apify `directUrls`
  URL refresh (`refresh_urls.py`).
- **Run 2 (invalid, AUC 0.08):** `social_posts` is 74% non-brand rows
  (retailers/influencers); the label measured account size. Fix: owner filter.
- **Run 3 (valid baseline):** brand-only, 30/30, judge AUC 0.63, rho 0.29.
  brand_strength carried the signal (rho 0.45); attention_capture (-0.19) and
  message_clarity (-0.16) slightly anti-predictive for organic.
- **Prompt anchors:** in-feed calibration section grounded in the run-3
  misses (teaser minimalism, shot-on imagery, meme formats vs polished
  showcase craft). In-sample AUC 0.63 -> 0.79, but holdout 0.59: the anchors
  fit the design set, they do not generalize. Prompt surgery has hit its
  ceiling on this task.
- **Reliability (46-call harness, run 20260728-151554):** anchors did not
  destabilize the judge. Displayed-score retest std 0.25/0.05 (PASS), funnel
  stable, invariance PASS; distinctiveness single-call std 0.70 remains the
  weak spot (mitigated in production by the median-of-3 ensemble). One soft
  flag: slight blur not penalized.
- **Ranker (eval/finetune/):** LoRA r=16 + scalar head on Qwen2.5-VL-3B,
  Bradley-Terry pairwise loss on the 60 design images (900 pairs), one A10G
  run. Train AUC 1.0 (memorized, expected), **holdout 0.838**. Adapter in
  Modal volume `fixation-ranker`.
- **KPI weight refit (eval/finetune/analyze_weights.py):** brand_strength
  dominant (+1.11), attention_capture (-0.35) and message_clarity (-0.37)
  negative. Holdout AUC 0.694 vs 0.591 deployed — a +0.10 gain available
  without touching any model.

## Caveats

- Organic engagement proxies paid performance imperfectly (no spend, no
  targeting, algorithmic reach). Read direction, not absolute calibration.
- Single account, single platform, images only; most brand content is reels
  (56-92% of extreme-quartile "image" rows were actually videos).
- Ranker holdout shares the account/context with training; cross-brand
  generalization unmeasured. Train AUC 1.0 says it will overfit hard as is;
  more data before trusting it further.

## Recommended next steps

1. **Grow the labeled set** — score the remaining ~350 aged brand-image
   candidates (queues still hold them) and re-train the ranker on the larger
   set with a proper val split; target holdout AUC >= 0.85 with train/holdout
   gap closing.
2. **Ship an organic-context weighting profile** (product decision): the
   refit weights are a validated +0.10 AUC for social-organic use; keep the
   current weights for paid-KV assessment.
3. **Reels support** — most Samsung social content is video; an image-only
   scorer misses the majority class.
4. **Ranker as a KPI** — expose the ranker score as a new "organic
   engagement" signal alongside the judge KPIs rather than replacing them.
