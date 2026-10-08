# Sprinklr multi-platform ranker — first results (2026-10-08)

Data: 2,421 Samsung-owned-account creatives (YT 773 / IG 778 / FB 870,
Jan-Sep 2026) with engagement-rate percentiles in platform x account x
quarter cohorts (paid-robust design; no paid flag exists in the export).
Frozen holdout: 396 (132/platform). Base: CreativeRanking-pretrained
Qwen3-VL-4B. Spend: $12.97 Apify.

| metric | value |
|---|---|
| zero-shot (CR pretrain only) | 0.478 — chance; this domain was learned from scratch |
| **holdout AUC (396, top-vs-bottom)** | **0.811** |
| per-platform | YouTube **0.981** / Instagram 0.671 / Facebook 0.656 |

## Calibration (the product sentence)

| score bucket | n | landed top-quartile |
|---|---|---|
| 6+ | 61 | **88.5%** |
| 4-6 | 219 | 60.7% |
| <4 | 116 | **9.5%** |

"Scores 6+: ~9-in-10 were real top-quartile performers; below 4: ~1-in-10."

## Caveats

- YouTube 0.981 is partly content-identity: thumbnails encode series/
  category, and some series systematically outperform. It predicts well
  but conflates "winning content type" with "winning creative execution".
  FB/IG (0.65-0.67) are the honest creative-execution numbers.
- Labels mix paid and organic (no flag available); rate + account-cohort
  design mitigates but cannot fully remove boost effects.

## Caption effects (train split, Spearman vs percentile)

hashtags +0.24, length +0.155, emoji +0.139, question-mark +0.065 —
hashtag count is the strongest caption lever; worth A/B testing first.

## Status

Model parked at eval/sprinklr/out/ (adapter, head, calibration.json) —
NOT serving. Integration decision pending: this is an account-aware
multi-platform scorer for Samsung-owned channels, complementary to the
production organic ranker (0.921 on brand-account IG organic).
