"""Tier-1 reliability harness for the F1X8 engagement judge.

Replays the exact production judge call from modal_app.py `assess_engagement()`
(claude-opus-4-8 + ENGAGEMENT_PROMPT + image) through the Anthropic Batches API
(50% price) and measures:

  1. Test-retest   — same image N times: per-KPI spread, funnel flips,
                     three_second_pass flips, displayed-score swing.
  2. Invariance    — benign transforms (JPEG re-encode, 90% resize) should
                     not move scores.
  3. Monotonicity  — degraded variants (blur, contrast crush, occlusion)
                     should score lower than the original.

The engagement prompt is extracted from modal_app.py at run time via AST so the
harness always tests exactly what is deployed. Requires ANTHROPIC_API_KEY when
run directly; use eval/modal_runner.py to run with the Modal `anthropic` secret.

Usage (local, with key):
    python3 eval/judge_reliability.py submit  [--images-dir eval/assets]
    python3 eval/judge_reliability.py status  --run eval/runs/<ts>
    python3 eval/judge_reliability.py report  --run eval/runs/<ts>
"""

import argparse
import ast
import base64
import io
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODAL_APP_PATH = os.path.join(REPO_ROOT, "modal_app.py")

# Mirrors production exactly (modal_app.py assess_engagement)
JUDGE_MODEL = "claude-opus-4-8"
JUDGE_MAX_TOKENS = 1500
JUDGE_USER_TEXT = "Assess this advertising asset for engagement potential. Return only the JSON object."

JUDGED_KPIS = ["emotional_pull", "brand_strength", "distinctiveness",
               "persuasive_power", "trust_credibility"]

# Copied from modal_app.py _FUNNEL_WEIGHTS / _FUNNEL_SELECT — used only to
# simulate the displayed engagement_potential with CV KPIs pinned at 6.0,
# isolating how much the judge alone moves the number the website shows.
FUNNEL_WEIGHTS = {
    "upper": {"attention_capture": .28, "emotional_pull": .28, "brand_strength": .18, "distinctiveness": .14, "message_clarity": .12},
    "lower": {"persuasive_power": .34, "message_clarity": .22, "attention_capture": .18, "trust_credibility": .16, "brand_strength": .10},
    "mid": {"attention_capture": .22, "persuasive_power": .22, "message_clarity": .20, "emotional_pull": .18, "brand_strength": .18},
}
CV_PIN = 6.0  # stand-in for the deterministic attention_capture / message_clarity

INVARIANCE_VARIANTS = ["jpeg85", "resize90"]
DEGRADED_VARIANTS = ["blur", "lowcontrast", "occlude"]


# ── Production-prompt extraction ──────────────────────────────────────────────

def _extract_assign(name, required=True):
    """Pull a top-level literal assignment out of modal_app.py without importing it."""
    with open(MODAL_APP_PATH, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    if required:
        raise RuntimeError(f"{name} not found in modal_app.py")
    return None


def load_engagement_prompt():
    return _extract_assign("ENGAGEMENT_PROMPT")


def load_engagement_schema():
    """Structured-output schema; None if the deployed app predates it."""
    return _extract_assign("ENGAGEMENT_SCHEMA", required=False)


# ── Variant generation ────────────────────────────────────────────────────────

def make_variants(img_bytes):
    """name -> jpeg bytes. 'original' + invariance + degradation variants."""
    from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    W, H = img.size

    def enc(im, q=92):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        return buf.getvalue()

    variants = {"original": enc(img)}
    # Invariance: should NOT change scores
    variants["jpeg85"] = enc(img, q=85)
    variants["resize90"] = enc(img.resize((int(W * .9), int(H * .9)), Image.LANCZOS))
    # Degradations: SHOULD lower scores
    variants["blur"] = enc(img.filter(ImageFilter.GaussianBlur(radius=max(2, W // 250))))
    variants["lowcontrast"] = enc(ImageEnhance.Contrast(img).enhance(0.45))
    occ = img.copy()
    d = ImageDraw.Draw(occ)
    d.rectangle([int(W * .08), int(H * .06), int(W * .72), int(H * .30)], fill="#333333")
    variants["occlude"] = enc(occ)
    return variants


def synth_sample_ads(assets_dir):
    """Two mock KVs (brand-led + offer-led) so the harness is runnable before
    real Samsung-category creatives are dropped into eval/assets/."""
    from PIL import Image, ImageDraw, ImageFont

    def font(sz):
        try:
            return ImageFont.load_default(size=sz)
        except TypeError:
            return ImageFont.load_default()

    os.makedirs(assets_dir, exist_ok=True)

    # Upper-funnel brand KV
    im = Image.new("RGB", (1080, 1350), "#0d1b2a")
    d = ImageDraw.Draw(im)
    d.rectangle([340, 420, 740, 980], fill="#1b3a5c", outline="#e0e1dd", width=3)
    d.ellipse([460, 540, 620, 700], fill="#415a77")
    d.text((90, 120), "SEE BEYOND", font=font(90), fill="#e0e1dd")
    d.text((90, 240), "the ordinary", font=font(60), fill="#778da9")
    d.text((90, 1230), "NOVA  |  Galaxy Vision", font=font(40), fill="#e0e1dd")
    im.save(os.path.join(assets_dir, "sample_brand_kv.jpg"), "JPEG", quality=92)

    # Lower-funnel offer KV
    im = Image.new("RGB", (1080, 1350), "#f5f5f0")
    d = ImageDraw.Draw(im)
    d.rectangle([600, 380, 1000, 900], fill="#dcdcd4", outline="#111111", width=3)
    d.text((70, 100), "50% OFF", font=font(120), fill="#c1121f")
    d.text((70, 260), "This weekend only", font=font(55), fill="#111111")
    d.text((70, 950), "Free shipping over $49", font=font(45), fill="#333333")
    d.rectangle([70, 1080, 520, 1180], fill="#c1121f")
    d.text((110, 1105), "SHOP NOW", font=font(50), fill="#ffffff")
    d.text((70, 1260), "NOVA  |  nova.example/sale", font=font(38), fill="#555555")
    im.save(os.path.join(assets_dir, "sample_offer_kv.jpg"), "JPEG", quality=92)


# ── Manifest + batch request construction ─────────────────────────────────────

def build_run(images_dir, run_dir, repeats=8, variant_repeats=3):
    """Returns (manifest, requests). Writes variants + manifest into run_dir."""
    prompt = load_engagement_prompt()
    schema = load_engagement_schema()
    names = sorted(f for f in os.listdir(images_dir)
                   if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    if not names:
        raise SystemExit(f"No images in {images_dir}")

    os.makedirs(os.path.join(run_dir, "variants"), exist_ok=True)
    manifest, requests = {}, []
    for name in names:
        stem = os.path.splitext(name)[0]
        with open(os.path.join(images_dir, name), "rb") as f:
            variants = make_variants(f.read())
        for vname, vbytes in variants.items():
            with open(os.path.join(run_dir, "variants", f"{stem}__{vname}.jpg"), "wb") as f:
                f.write(vbytes)
            n = repeats if vname == "original" else variant_repeats
            b64 = base64.b64encode(vbytes).decode()
            for i in range(n):
                cid = f"{stem}__{vname}__r{i}"
                manifest[cid] = {"image": stem, "variant": vname, "repeat": i}
                extra = {}
                if schema is not None:  # mirror production's structured output
                    extra["output_config"] = {"format": {"type": "json_schema",
                                                         "schema": schema}}
                requests.append({
                    "custom_id": cid,
                    "params": {
                        **extra,
                        "model": JUDGE_MODEL,
                        "max_tokens": JUDGE_MAX_TOKENS,
                        # cache_control is best-effort: batch requests run
                        # concurrently so hits aren't guaranteed; the reliable
                        # saving is the 50% batch discount.
                        "system": [{"type": "text", "text": prompt,
                                    "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
                        "messages": [{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64",
                                                         "media_type": "image/jpeg",
                                                         "data": b64}},
                            {"type": "text", "text": JUDGE_USER_TEXT},
                        ]}],
                    },
                })
    with open(os.path.join(run_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest, requests


# ── Response parsing (port of modal_app.py _parse_engagement_json) ────────────

def parse_engagement(text):
    if not text:
        return None
    try:
        t = text.strip()
        if t.startswith("```"):
            t = t.split("```", 2)[1] if "```" in t[3:] else t.lstrip("`")
            if t.startswith("json"):
                t = t[4:]
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end == -1:
            return None
        t = t[start:end + 1]
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            # mirror production's trailing-comma repair
            import re
            return json.loads(re.sub(r",(\s*[}\]])", r"\1", t))
    except Exception:
        return None


def simulated_score(judgment):
    """engagement_potential as the site would compute it, with the two
    CV-derived KPIs pinned at CV_PIN — isolates judge-driven movement."""
    stage = judgment.get("funnel_stage")
    if stage not in FUNNEL_WEIGHTS:
        stage = "mid"
    clarity = CV_PIN
    if (judgment.get("message_clarity_judgment") or {}).get("three_second_pass") is False:
        clarity *= 0.85
    def kpi(name):
        if name == "attention_capture":
            return CV_PIN
        if name == "message_clarity":
            return clarity
        try:
            return float((judgment.get(name) or {}).get("score", 5))
        except (TypeError, ValueError):
            return 5.0
    return round(sum(kpi(k) * w for k, w in FUNNEL_WEIGHTS[stage].items()), 2)


# ── Report ────────────────────────────────────────────────────────────────────

def _grade(std):
    return "PASS" if std < 0.35 else ("WARN" if std < 0.75 else "FAIL")


def write_report(run_dir):
    with open(os.path.join(run_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(run_dir, "results.json")) as f:
        results = json.load(f)

    parsed = {}
    failures = []
    usage_in = usage_out = 0
    for cid, res in results.items():
        usage_in += res.get("usage", {}).get("input_tokens", 0) or 0
        usage_out += res.get("usage", {}).get("output_tokens", 0) or 0
        j = parse_engagement(res.get("text")) if res.get("ok") else None
        if j is None:
            failures.append(cid)
        else:
            parsed[cid] = j

    by_group = {}
    for cid, meta in manifest.items():
        if cid in parsed:
            by_group.setdefault((meta["image"], meta["variant"]), []).append(parsed[cid])

    lines = [f"# Judge reliability report — {os.path.basename(run_dir)}",
             "",
             f"Model `{JUDGE_MODEL}` · prompt extracted from `modal_app.py` · "
             f"{len(results)} calls, {len(failures)} parse/API failures",
             ""]
    if failures:
        lines += ["Failed custom_ids: " + ", ".join(failures[:10]) +
                  (" …" if len(failures) > 10 else ""), ""]

    images = sorted({m["image"] for m in manifest.values()})
    overall_flags = []

    for img in images:
        orig = by_group.get((img, "original"), [])
        lines += [f"## {img}", ""]
        if len(orig) < 2:
            lines += ["Not enough successful original runs to analyze.", ""]
            continue

        # 1. Test-retest
        lines += [f"### Test–retest (n={len(orig)})", "",
                  "| metric | mean | std | min | max | grade |",
                  "|---|---|---|---|---|---|"]
        for k in JUDGED_KPIS:
            vals = [float((j.get(k) or {}).get("score", 5)) for j in orig]
            std = statistics.pstdev(vals)
            lines.append(f"| {k} | {statistics.mean(vals):.2f} | {std:.2f} | "
                         f"{min(vals):.1f} | {max(vals):.1f} | {_grade(std)} |")
            if _grade(std) == "FAIL":
                overall_flags.append(f"{img}: {k} retest std {std:.2f}")
        sims = [simulated_score(j) for j in orig]
        sim_std = statistics.pstdev(sims)
        lines.append(f"| **displayed score (sim)** | {statistics.mean(sims):.2f} | {sim_std:.2f} | "
                     f"{min(sims):.2f} | {max(sims):.2f} | {_grade(sim_std)} |")
        funnels = [j.get("funnel_stage") for j in orig]
        flips = len(set(funnels)) - 1
        passes = [(j.get("message_clarity_judgment") or {}).get("three_second_pass") for j in orig]
        lines += ["",
                  f"- funnel_stage across runs: {dict((f, funnels.count(f)) for f in set(funnels))}"
                  f" — {'STABLE' if flips == 0 else f'{flips} FLIP(S) — weights change between runs!'}",
                  f"- three_second_pass across runs: {dict((str(p), passes.count(p)) for p in set(passes))}",
                  ""]
        if flips:
            overall_flags.append(f"{img}: funnel_stage flips {set(funnels)}")

        orig_mean = statistics.mean(sims)

        # 2. Invariance
        lines += ["### Invariance (benign transforms — Δ should be ≈ 0)", "",
                  "| variant | n | sim score mean | Δ vs original | verdict |",
                  "|---|---|---|---|---|"]
        for v in INVARIANCE_VARIANTS:
            runs = by_group.get((img, v), [])
            if not runs:
                lines.append(f"| {v} | 0 | — | — | NO DATA |")
                continue
            m = statistics.mean(simulated_score(j) for j in runs)
            d = m - orig_mean
            verdict = "PASS" if abs(d) < 0.4 else ("WARN" if abs(d) < 0.8 else "FAIL")
            lines.append(f"| {v} | {len(runs)} | {m:.2f} | {d:+.2f} | {verdict} |")
            if verdict == "FAIL":
                overall_flags.append(f"{img}: invariance {v} Δ{d:+.2f}")
        lines.append("")

        # 3. Monotonicity
        lines += ["### Monotonicity (degradations — score should drop)", "",
                  "| variant | n | sim score mean | Δ vs original | verdict |",
                  "|---|---|---|---|---|"]
        for v in DEGRADED_VARIANTS:
            runs = by_group.get((img, v), [])
            if not runs:
                lines.append(f"| {v} | 0 | — | — | NO DATA |")
                continue
            m = statistics.mean(simulated_score(j) for j in runs)
            d = m - orig_mean
            verdict = "PASS" if d < -0.3 else ("WARN" if d < 0.1 else "FAIL (scored higher!)")
            lines.append(f"| {v} | {len(runs)} | {m:.2f} | {d:+.2f} | {verdict} |")
            if verdict.startswith("FAIL"):
                overall_flags.append(f"{img}: degradation {v} not penalized (Δ{d:+.2f})")
        lines.append("")

    # Cost (batch = 50% of $5/$25 per MTok for Opus 4.8)
    cost = usage_in / 1e6 * 2.5 + usage_out / 1e6 * 12.5
    lines += ["## Run cost", "",
              f"- input tokens: {usage_in:,} · output tokens: {usage_out:,}",
              f"- batch-discounted cost: **${cost:.2f}**", ""]

    lines += ["## Flags", ""]
    lines += [f"- {f}" for f in overall_flags] if overall_flags else ["- none 🎉"]
    lines.append("")

    report_path = os.path.join(run_dir, "REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path


# ── Local CLI (needs ANTHROPIC_API_KEY; modal_runner.py is the keyless path) ──

def _client():
    import anthropic
    return anthropic.Anthropic()


def cmd_submit(args):
    run_dir = os.path.join(REPO_ROOT, "eval", "runs",
                           datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    if not os.path.isdir(args.images_dir) or not os.listdir(args.images_dir):
        print(f"{args.images_dir} empty — generating synthetic sample KVs")
        synth_sample_ads(args.images_dir)
    manifest, requests = build_run(args.images_dir, run_dir,
                                   args.repeats, args.variant_repeats)
    print(f"{len(requests)} requests → submitting batch…")
    batch = _client().messages.batches.create(requests=requests)
    with open(os.path.join(run_dir, "batch_id.txt"), "w") as f:
        f.write(batch.id)
    print(f"Batch {batch.id} submitted. Run dir: {run_dir}")


def cmd_status(args):
    with open(os.path.join(args.run, "batch_id.txt")) as f:
        bid = f.read().strip()
    b = _client().messages.batches.retrieve(bid)
    print(b.processing_status, b.request_counts)


def cmd_report(args):
    results_path = os.path.join(args.run, "results.json")
    if not os.path.exists(results_path):
        with open(os.path.join(args.run, "batch_id.txt")) as f:
            bid = f.read().strip()
        client = _client()
        out = {}
        for r in client.messages.batches.results(bid):
            if r.result.type == "succeeded":
                msg = r.result.message
                out[r.custom_id] = {
                    "ok": True,
                    "text": next((b.text for b in msg.content if b.type == "text"), ""),
                    "usage": {"input_tokens": msg.usage.input_tokens,
                              "output_tokens": msg.usage.output_tokens},
                }
            else:
                out[r.custom_id] = {"ok": False, "error": r.result.type}
        with open(results_path, "w") as f:
            json.dump(out, f, indent=2)
    print("Report:", write_report(args.run))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--images-dir", default=os.path.join(REPO_ROOT, "eval", "assets"))
    s.add_argument("--repeats", type=int, default=8)
    s.add_argument("--variant-repeats", type=int, default=3)
    s.set_defaults(fn=cmd_submit)
    for name, fn in (("status", cmd_status), ("report", cmd_report)):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.set_defaults(fn=fn)
    a = p.parse_args()
    a.fn(a)
