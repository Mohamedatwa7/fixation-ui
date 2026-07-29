# Engagement-score calibration & fine-tune findings — 2026-07-28/29

Two-day study: does the deployed Engagement Potential score track realized
organic engagement on @samsunggulf Instagram image creatives, and what is the
best path to making it accurate? All AUCs are top-vs-bottom quartile
discrimination (0.5 = chance) on cohort-normalized engagement percentiles.

## Headline: holdout leaderboard (n=82 unseen creatives)

| scorer | holdout AUC |
|---|---|
| **Qwen2.5-VL-3B LoRA ranker, 142 train images (2026-07-29)** | **0.851** |
| Qwen2.5-VL-3B LoRA ranker, 60 train images (first run) | 0.838 |
| Judge KPIs, holdout-validated refit weights | 0.694 |
| Judge brand_strength KPI alone | 0.609 |
| Deployed judge score (median-of-3 ensemble, anchored prompt) | 0.591 |

## Shipped (2026-07-29)

- **`organic_engagement` response field** on the main API (additive; funnel
  score and KPI cards untouched): sigmoid-squashed refit-weight combo,
  constants from the 142-creative sample. Verified live.
- **Ranker serving endpoint** `https://mohamedymay7--rank.modal.run`
  (separate Modal app `fixation-ranker-api`, A10G, volume-loaded adapter):
  POST JSON `{"image_b64": ...}` -> `{"rank_score": 0-10}`. Verified live
  (known top creative 8.05 vs known dud 3.25).
- **Data scaling**: strata widened to 60/40 bands (STRATA_TOP/STRATA_BOTTOM
  env), percentile-gap (>=30) pairwise training; train set 60 -> 142 images,
  holdout frozen at the original 82 for comparability. Retrain: holdout AUC
  0.838 -> 0.851 — the data-scaling curve is positive; more images should
  keep helping.

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

## Phase-2 results (2026-07-29, second session)

- **media_kind root-cause fix**: IG reels carry .jpg thumbnails as media_url
  and were classified as images. The brand pool is really **265 images +
  ~719 reels**, not 984 images. Image cohorts are now decontaminated; the
  ranker re-baselines at **0.850** on the 62 still-valid holdout creatives
  (zero strata flips) — the benchmark survives.
- **Reels calibration (n=36 brand reels via the deployed video pipeline):
  AUC 0.731, Spearman 0.38** — the video path discriminates the majority
  content class better than the image judge does images. Likely helped by
  per-view label basis on videos. 4/40 pipeline errors.
- **Cross-account validation (xcitealghanim retailer, n=80, 40/40): ranker
  AUC 0.621** — transfers weakly-positively; the adapter carries real
  general signal plus substantial Samsung-specific aesthetics. Multi-account
  training data is the path to a general model.
- **Weekly retrain loop built** (`weekly_retrain.py` + promote-on-improvement
  in the trainer; adapter only reaches the serving volume path when holdout
  AUC clears the best-so-far bar). Task Scheduler registration pending user
  approval (`run_weekly.cmd`).
- **UI**: Organic chip shipped on the results verdict panel.

## Recommended next steps

1. ~~Grow the labeled set~~ — done to queue exhaustion (224 images with live
   URLs; brand image pool is ~984 but CDN expiry caps what is retrievable).
   Next data unlock: ingest fresh nightly scrapes as they mature past 14
   days (each week adds mature posts with live URLs), and periodically
   re-run the refresh + retrain loop.
2. ~~Ship an organic-context weighting profile~~ — shipped as the additive
   `organic_engagement` field.
3. ~~Reels support phase 1~~ — measured (AUC 0.731 via existing video
   pipeline). Phase 2: reels ranker (train on sampled frames or cover +
   motion features) and reels-aware UI.
4. ~~Ranker as a KPI~~ — served at the standalone endpoint; Organic chip
   shipped. A dedicated rank_score card wired to the ranker endpoint remains
   optional UI work.
5. ~~Cross-brand validation phase 1~~ — measured (0.621 on a retailer feed).
   Phase 2: add non-brand accounts' extremes to ranker training for a
   general model (the export already holds 12.5k non-brand posts).
6. **Weekly retrain loop** — built; register the scheduled task (user
   approval), then let it run. Extend it to reels once the reels ranker
   exists.
