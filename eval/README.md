# F1X8 judge reliability harness (tier 1)

Measures whether the engagement judge — the Claude call in `modal_app.py`
`assess_engagement()` that drives the website's displayed score — is stable,
invariant to benign transforms, and correctly penalizes degraded creatives.
Runs through the Anthropic **Batches API** (50% price); the engagement prompt is
extracted from `modal_app.py` at run time so the harness always tests what is
deployed.

## Run it

No local API key needed (uses the Modal `anthropic` secret):

```sh
python3 -m modal run eval/modal_runner.py                        # sample KVs
python3 -m modal run eval/modal_runner.py --images-dir path/to/kvs
python3 -m modal run eval/modal_runner.py --fetch-run eval/runs/<ts>   # resume
```

With a local `ANTHROPIC_API_KEY`, `eval/judge_reliability.py` has
`submit` / `status` / `report` subcommands directly.

Put real Samsung-category KVs (jpg/png/webp) in `eval/assets/` — the two
`sample_*` images are synthetic placeholders generated on first run.

## What a run does

Per image: 8× the untouched original (test–retest), plus 3× each of five
variants — `jpeg85`, `resize90` (invariance: scores should not move) and
`blur`, `lowcontrast`, `occlude` (degradations: scores should drop).

`eval/runs/<ts>/REPORT.md` grades:

- **Test–retest** — per-KPI std across identical runs, funnel_stage flips
  (a flip changes the KPI weighting the site uses!), three_second_pass flips,
  and the swing in a simulated displayed score (CV KPIs pinned at 6.0 so only
  judge movement shows).
- **Invariance** — |Δ| vs original mean per benign transform.
- **Monotonicity** — degraded variants must score below the original.
- **Cost** — actual token usage priced at batch rates.

Grades: std < 0.35 PASS · < 0.75 WARN · else FAIL.

## Reading the results → what to fix

- High retest std / funnel flips → add self-consistency (median-of-N judge
  calls) in `assess_engagement()` and tighten per-KPI rubric anchors in the
  engagement prompt.
- Invariance failures → judge is reacting to pixels/encoding, not creative
  content; consider normalizing inputs (fixed max resolution) before judging.
- Monotonicity failures → the prompt's scoring anchors aren't grounded enough;
  add explicit "what a 3 vs 7 looks like" anchors per KPI.

Re-run after every prompt change and diff REPORT.md — this is the regression
gate for scoring work.
