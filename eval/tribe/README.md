# TRIBE v2 × F1X8 — neural-response validation experiment

Does Meta's TRIBE v2 brain-response encoder add predictive power for **realized
organic engagement** beyond F1X8's existing signals (gaze saliency, CV KPIs,
LLM judge)? This harness runs the encoder over the labeled calibration set and
measures the incremental lift.

TRIBE v2 is CC BY-NC — this use is research-only, consistent with the license.
Weights: `facebook/tribev2` · Code: `facebookresearch/tribev2`.

## Pipeline

1. `python eval/tribe/build_manifest.py`
   — collects labeled creatives: 224 local calibration images + the 40 reels
   already scored by the video pipeline (re-fetched by post URL at runtime).
2. `modal run eval/tribe/modal_tribe.py --smoke true`
   — 2 images + 1 reel end-to-end (first run also downloads weights into the
   `tribe-cache` volume).
3. `modal run eval/tribe/modal_tribe.py`
   — full extraction on A100s; resumable (done ids skipped); writes
   `features.json`.
4. `python eval/tribe/refit_with_tribe.py`
   — stratified 5-fold CV AUC: baseline score alone vs baseline + TRIBE
   features, per media kind. The decision gate: TRIBE earns a place in the
   product pipeline only if the delta is a real lift (≳ +0.03).

## Feature reduction

TRIBE predicts `(n_timesteps, ~20k fsaverage5 vertices)`. We map vertices to
the Yeo 7 networks via the Schaefer-400 surface parcellation (CBIG) and keep,
per network (Vis, SomMot, DorsAttn, SalVentAttn, Limbic, Cont, Default):
mean, peak, std, early mean (first 20%), late mean (last 20%) — plus global
mean/std. 37 features per creative.

Still images are looped into a 12s silent mp4; reels are capped at 120s.

## Findings — 2026-08-31 (complete): do not integrate

Extraction: 224/224 images; 33/40 reels in BOTH text modes (`av` = Word
events dropped, no gated repo needed; `avt` = full tri-modal with a
Llama-3.2-licensed HF token). 7 reels unrecoverable behind IG auth walls.

**Image arm (n=141): no signal.** Baseline 0.645 CV AUC; all 37 TRIBE
features 0.621 (−0.024); best case (7 network means, tuned L2) 0.653
(+0.008). Individual networks 0.51–0.55 — near-chance.

**Video arm (n=30): no signal, and the av-mode teaser did not replicate.**

| video model | 5-fold CV AUC |
|---|---|
| baseline (pipeline score) alone | 0.725 |
| + 14 TRIBE features, av mode | 0.483 (−0.242) |
| + 14 TRIBE features, avt mode | 0.408 (−0.317) |

In av mode, Limbic_std and Default_std each hit 0.713 univariate — but
that is what the best of 14 tested features looks like under noise at
n=30, and both collapsed (0.611 / 0.579) when the text pathway was added
in avt mode. No feature in the full model exceeds 0.61 alone; every
multivariate combination underperforms the baseline.

**Decision (per the pre-registered gate): TRIBE v2 does not enter the
F1X8 pipeline.** Predicted population-level cortical response, reduced to
network summaries, carries no measurable information about realized
in-feed engagement beyond what the gaze + judge + calibration stack
already captures — on this sample. Power caveat: n=30 videos cannot
detect small effects; the harness is resumable and the analysis rerunnable
if the labeled reel set grows or Meta ships a stronger encoder.

## Caveats

- TRIBE models *cortical* response of an average subject trained on passive
  movie/podcast viewing — not feed-scrolling, not a Gulf-region audience, and
  deep reward structures are not covered.
- Static images as looped video are off-distribution for the encoder; treat
  image-side features with extra skepticism.
- The refit uses 5-fold CV rather than the frozen 82-image holdout, so numbers
  are not directly comparable to FINDINGS.md — compare deltas, not levels.
