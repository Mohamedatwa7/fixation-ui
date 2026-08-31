# Paid-performance validation seed — FF8 preorder (Meta), 2026-08-31

`ff8_preorder_meta.csv`: 12 assets from the Fold8/Flip8 pre-order Meta
campaigns (impressions, link clicks, CPM, CTR, VTR, ER), transcribed from the
media team's export. Four statics were scored through the deployed F1X8
pipeline (ranker-backed organic + EP); the remaining eight creative files are
not currently available.

## Findings (n=4 scored, within-campaign pairs only)

Cross-campaign comparison is invalid — upper vs lower funnel ran with 2-6x
CPM differences driven by objective/audience. Within campaign:

- **Upper statics — F1X8 wrong, decisively.** Ranked flip8 (7.1) over the
  fold8 duo (6.6); the duo did 6x the CTR (0.85 vs 0.14) and 5x the ER in the
  same tier. The duo — hands, both devices, visible offer — is exactly the
  info-dense, offer-forward profile the organic-trained ranker reads as
  "cluttered template".
- **Lower statics — F1X8 marginally wrong.** Preferred ultra (7.6) over hero
  (6.7); actuals: hero 0.65% ER / 0.58% CTR vs ultra 0.55% / 0.47% at similar
  CPMs.

**Hypothesis to test when more paid data lands:** the ranker (trained on
organic brand-feed engagement) systematically undervalues offer-forward,
information-dense executions that win in paid delivery. If confirmed, F1X8
needs a paid-mode calibration (CTR/ER labels, statics and videos separate —
video ER is VTR-inflated 4-15% and not comparable to static ER).

## What unblocks the real validation

Creative files matched to asset codes (Meta Ads Manager retains them under
Ads -> Creative, or the media agency's asset library), for this and future
campaigns, alongside the performance export. ~20-30 labeled paid assets is
enough for a first calibration pass.
