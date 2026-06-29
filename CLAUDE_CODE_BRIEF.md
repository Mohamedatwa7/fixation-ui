# Claude Code Brief: Funnel-Aware Engagement Scoring for F1X8

## Goal
Add a funnel-aware "Engagement Potential" score to F1X8. The score predicts how likely a creative is to earn engagement, and it is weighted by funnel stage so that offer-driven conversion assets and emotional awareness assets are each judged against the right standard. The 5 KPIs shown to the user CHANGE depending on the asset's funnel stage.

Do NOT rewrite the working pipeline. The image and video analysis already run end to end and render results. You are ADDING a scoring/aggregation layer and adapting how KPIs are displayed.

## Before you change anything
1. Read `modal_app.py` fully. Note how the image endpoint and the video job currently build their response (the `kpis`, `score`, `kpis_overall`, `verdict` fields).
2. Read `lib/api.ts`. Note the `adaptResult` function and how `kpis` is mapped into the UI shape.
3. Read `components/results/VerdictBlock.tsx` and the KPI breakdown component under `components/results/`. Note how `result.score` and `result.kpis` render.
4. Read `lib/mock-data.ts` for the `DiagnosticResult`, `KPI`, and `Risk` interfaces.
Confirm you understand the current shapes before editing.

## Architecture of the change
The backend already computes MEASURED KPIs from computer vision (these stay):
- Image measured KPI keys: `hierarchy`, `composition`, `white_space`, `color_contrast`, `visual_complexity`, `text_balance`. Each is an object with a `score` (0-10) plus `label`, `methodology`, `percentile`.
- Video measured KPI keys: `cognitive_load`, `pattern_interrupt`, `first_fixation`, `switching_cost`, `hook`, `anchor_stability`. Each has a `score` (0-10).

Add a focused LLM engagement assessment that supplies the non-measurable judgments. The prompt is in `f1x8_engagement_prompt.txt` (place it in the repo root or `lib/`). It returns funnel_stage, product_tier, asset_intent, and scores for emotional_pull, brand_strength, distinctiveness, persuasive_power, trust_credibility, plus a three_second_pass flag.

Then aggregate measured signals + LLM judgment into 5 funnel-specific KPIs and one Engagement Potential score.

## Step 1: Add the engagement assessment call (backend, modal_app.py)
Add a function that sends the asset to a vision LLM with the engagement prompt and parses the JSON.
- Use the Anthropic API (the `anthropic` package and the `anthropic` Modal secret are already configured). Send the image as a base64 image block for image assets. For video, send 3 evenly-spaced keyframes (the video pipeline already extracts keyframes; reuse them, or sample 3 frames with cv2).
- System prompt = contents of `f1x8_engagement_prompt.txt`.
- Parse the returned JSON robustly (strip any accidental code fences, `json.loads`). On failure, return a neutral default with all judgment scores = 5 and funnel_stage = "mid" so the pipeline never crashes.
- Call this in BOTH the image endpoint and the video job, after the measured KPIs are computed.

## Step 2: Add the aggregation (backend, a new top-level function in modal_app.py)
Map measured KPIs + LLM judgment into the 5 funnel KPIs, then compute Engagement Potential.

Compute the two UNIVERSAL measured KPIs first:
- Attention Capture:
  - Image: weighted blend of measured scores -> hierarchy 0.5, color_contrast 0.3, composition 0.2
  - Video: blend -> first_fixation 0.4, hook 0.3, pattern_interrupt 0.3
- Message Clarity:
  - Image: blend -> text_balance 0.4, visual_complexity 0.35, white_space 0.25
  - Video: blend -> cognitive_load 0.5, switching_cost 0.5
  - After blending, if LLM three_second_pass is false, multiply by 0.85.
Blend helper: sum(score * weight) over the keys that exist; if a key is missing, renormalize weights over present keys.

Take the three judgment KPIs directly from the LLM assessment:
- Emotional Pull = emotional_pull.score
- Brand Strength = brand_strength.score
- Distinctiveness = distinctiveness.score
- Persuasive Power = persuasive_power.score
- Trust & Credibility = trust_credibility.score

Select the 5 KPIs to surface by funnel_stage, and apply these weights for Engagement Potential:

UPPER:  attention_capture .28, emotional_pull .28, brand_strength .18, distinctiveness .14, message_clarity .12
LOWER:  persuasive_power .34, message_clarity .22, attention_capture .18, trust_credibility .16, brand_strength .10
MID:    attention_capture .22, persuasive_power .22, message_clarity .20, emotional_pull .18, brand_strength .18

Engagement Potential = round(sum(kpi_score * weight) for the 5 selected KPIs, 1).

Return in the endpoint/job response:
- `engagement_potential` (number, 0-10)
- `funnel_stage` (string)
- `kpis`: an object keyed by the 5 selected KPI ids, each `{ score, label, methodology }`. Use clear labels: "Attention Capture", "Message Clarity", "Emotional Pull", "Brand Strength", "Distinctiveness", "Persuasive Power", "Trust & Credibility". For methodology, use the measured KPI's methodology string for Attention/Clarity, and the LLM `reasoning` field for the judgment KPIs.
- Keep returning `verdict`, `heatmap`, `heatmap_type` as today.
- Keep `score` for backward compatibility, set it equal to `engagement_potential`.

## Step 3: Frontend pass-through (lib/api.ts)
In `adaptResult`:
- Set `score` from `engagement_potential` (fall back to existing `score`/`kpis_overall`).
- Carry `funnel_stage` onto the result object (extend the type if needed).
- `toKpiArray` should map the 5 returned KPIs as-is (they already have score, label, methodology). Do not invent labels; use what the backend sends.

## Step 4: Display (components/results)
- The headline number in `VerdictBlock.tsx` should be labeled "Engagement Potential" (not a generic score). Keep the existing PASS/REVIEW/FAIL band logic on the 0-10 value, but consider relabeling bands to "Strong / Moderate / Weak" engagement.
- Add a small funnel-stage pill near the verdict showing the detected funnel (e.g. "AWARENESS", "CONSIDERATION", "CONVERSION" mapped from upper/mid/lower).
- The KPI breakdown renders whatever 5 KPIs arrive. Since the set changes by funnel, do not hardcode KPI names in the component; render from the array. Keep the hover-for-methodology behaviour.

## Acceptance criteria
- An offer creative (e.g. a "Galaxy A57 50% off, ends Sunday" KV) is classified lower funnel, shows Attention Capture / Message Clarity / Persuasive Power / Trust & Credibility / Brand Strength, and scores high Engagement Potential driven by Persuasive Power.
- A pure-brand awareness KV is classified upper funnel, shows Attention Capture / Emotional Pull / Brand Strength / Distinctiveness / Message Clarity, is never asked about offers, and is not penalized for lacking one.
- Attention Capture and Message Clarity values trace back to the measured CV signals, not the LLM.
- The pipeline never crashes if the LLM JSON fails to parse (neutral defaults).
- Existing image and video analysis still render; nothing in the working flow regresses.

## Notes
- Keep the LLM engagement call lightweight (low max_tokens, it returns a small JSON). It is one extra call per analysis.
- Do not add browser storage. Result handoff already uses an in-memory store plus a slimmed sessionStorage fallback; leave that intact.
- After implementing, run the dev server and test one image and one video URL before declaring done.
