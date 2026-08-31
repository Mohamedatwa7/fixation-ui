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

## Findings — 2026-08-31 (image arm complete, video arm blocked)

Extraction: 228/264 ok — all 224 images, 4/40 reels. Reel failures: 29 hit
the gated `meta-llama` repo (TRIBE routes videos with detected speech through
its Llama text pipeline; needs an HF token with Llama 3.2 access), 7 hit
IG fetch auth walls.

**Image arm (n=141 labeled): TRIBE adds no signal.**

| model | 5-fold CV AUC |
|---|---|
| baseline score alone | 0.645 |
| + all 37 TRIBE features (lam=1) | 0.621 (−0.024) |
| + 7 network means (lam=10–50) | 0.653 (+0.008) |

Every network mean alone is near-chance vs realized engagement (AUC
0.51–0.55). Best case is +0.008 — far under the +0.03 gate. Verdict for
stills: **do not integrate**; consistent with the caveat that looped silent
stills are off-distribution for a movie-trained encoder.

**Video arm: n=4, unresolved** — this is where the hypothesis was always
strongest (temporal neural engagement vs watch-time). To complete it:
provide an HF token with the Llama 3.2 license accepted (`HF_TOKEN` env at
run time), then `modal run eval/tribe/modal_tribe.py --only-kind video`.

## Caveats

- TRIBE models *cortical* response of an average subject trained on passive
  movie/podcast viewing — not feed-scrolling, not a Gulf-region audience, and
  deep reward structures are not covered.
- Static images as looped video are off-distribution for the encoder; treat
  image-side features with extra skepticism.
- The refit uses 5-fold CV rather than the frozen 82-image holdout, so numbers
  are not directly comparable to FINDINGS.md — compare deltas, not levels.
