"""A/B: does AAM saliency improve the measurable-KPI signal vs OpenCV?

Scores every image in the calibration sample twice in lite mode (saliency +
design KPIs only — no Qwen, no Claude, no API cost): once with the legacy
OpenCV saliency, once with AAM (F1X8_SALIENCY=aam). Then compares each
pass's correlation with the cohort-normalized engagement percentiles using
the same metrics as REPORT.md (Spearman rho + top-vs-bottom AUC).

Run from the local_backend venv (needs torch + AAM deps):

    $env:AAM_REPO="D:\\content\\Attend-to-Anything"
    $env:AAM_WEIGHTS="D:\\F1X8\\local_backend\\weights\\AAM.pth"
    D:\\F1X8\\local_backend\\.venv\\Scripts\\python.exe eval/calibration/aam_ab.py

Outputs: data/aam_ab_results.json + data/REPORT-aam-ab.md. Resumable — per-
image scores are checkpointed after every image.
"""

import json
import os
import sys
import time

CAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CAL_DIR, "data")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
OUT_JSON = os.path.join(DATA_DIR, "aam_ab_results.json")
OUT_MD = os.path.join(DATA_DIR, "REPORT-aam-ab.md")
REPO = os.path.dirname(os.path.dirname(CAL_DIR))
BENCHMARK = os.path.join(REPO, "local_backend", "benchmarks",
                         "benchmark_online_percentiles.json")

sys.path.insert(0, os.path.join(REPO, "backend_scripts"))
sys.path.insert(0, CAL_DIR)


def rank(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx > 0 and dy > 0 else float("nan")


def auc(scores_pos, scores_neg):
    """P(score_top > score_bottom) with tie credit 0.5."""
    if not scores_pos or not scores_neg:
        return float("nan")
    wins = ties = 0
    for p in scores_pos:
        for q in scores_neg:
            if p > q:
                wins += 1
            elif p == q:
                ties += 1
    return (wins + 0.5 * ties) / (len(scores_pos) * len(scores_neg))


def load_items():
    with open(os.path.join(DATA_DIR, "dataset.json"), encoding="utf-8") as f:
        d = json.load(f)
    by_id = {p["id"]: p for p in d["posts"] if isinstance(p, dict) and "id" in p}
    items = []
    for sid in d["sample"]:
        post = by_id.get(sid)
        media = os.path.join(MEDIA_DIR, f"{sid}.jpg")
        if post and post.get("kind") == "image" and \
                post.get("percentile") is not None and os.path.exists(media):
            items.append({"id": sid, "path": media,
                          "percentile": float(post["percentile"])})
    return items


def score_pass(items, mode, state):
    """mode: 'legacy' or 'aam'. Returns {id: {overall, kpis{...}}}."""
    from analyze_image import compute_saliency_map
    from image_kpis import compute_image_kpis

    if mode == "aam":
        os.environ["F1X8_SALIENCY"] = "aam"
    else:
        os.environ.pop("F1X8_SALIENCY", None)

    done = state.setdefault(mode, {})
    todo = [it for it in items if it["id"] not in done]
    print(f"[{mode}] {len(todo)} to score ({len(done)} cached)")
    bench = BENCHMARK if os.path.exists(BENCHMARK) else None
    for n, it in enumerate(todo, 1):
        t0 = time.time()
        try:
            sal_map, _ = compute_saliency_map(it["path"])
            kpi = compute_image_kpis(it["path"], saliency_map=sal_map,
                                     benchmark_path=bench)
            done[it["id"]] = {
                "overall": kpi["overall"],
                "kpis": {k: v["score"] for k, v in kpi["kpis"].items()},
            }
        except Exception as e:
            print(f"[{mode}] {it['id']} FAILED: {e!r}")
            done[it["id"]] = {"error": str(e)}
        if n % 5 == 0 or n == len(todo):
            with open(OUT_JSON, "w", encoding="utf-8") as f:
                json.dump(state, f)
            print(f"[{mode}] {n}/{len(todo)} ({time.time()-t0:.1f}s/img)",
                  flush=True)
    return done


def analyze(items, state):
    lines = ["# AAM vs OpenCV saliency — KPI-signal A/B",
             "",
             f"Lite-mode (saliency + design KPIs, no judge) over "
             f"{len(items)} labeled calibration images; metric = agreement "
             f"with cohort-normalized engagement percentiles.", ""]
    pcts = {it["id"]: it["percentile"] for it in items}
    med = sorted(pcts.values())[len(pcts) // 2]
    result = {}
    for mode in ("legacy", "aam"):
        rows = [(sid, r) for sid, r in state.get(mode, {}).items()
                if "error" not in r and sid in pcts]
        xs = [r["overall"] for _, r in rows]
        ys = [pcts[sid] for sid, _ in rows]
        rho = spearman(xs, ys)
        top = [r["overall"] for sid, r in rows if pcts[sid] >= med]
        bot = [r["overall"] for sid, r in rows if pcts[sid] < med]
        a = auc(top, bot)
        kpi_rhos = {}
        for kid in rows[0][1]["kpis"]:
            kxs = [r["kpis"].get(kid) for _, r in rows]
            ok = [(x, y) for x, y in zip(kxs, ys) if isinstance(x, (int, float))]
            kpi_rhos[kid] = spearman([x for x, _ in ok], [y for _, y in ok])
        result[mode] = {"n": len(rows), "spearman_overall": round(rho, 3),
                        "auc_top_vs_bottom": round(a, 3),
                        "kpi_spearman": {k: round(v, 3) for k, v in kpi_rhos.items()}}
        lines += [f"## {mode}  (n={len(rows)})", "",
                  f"- Spearman rho (overall vs percentile): **{rho:.3f}**",
                  f"- AUC (top-half vs bottom-half): **{a:.3f}**",
                  "- Per-KPI Spearman: " + ", ".join(
                      f"{k}={v:.3f}" for k, v in sorted(kpi_rhos.items())), ""]
    # Per-image deltas for eyeballing which creatives moved most
    both = [sid for sid in state.get("legacy", {}) if sid in state.get("aam", {})
            and "error" not in state["legacy"][sid] and "error" not in state["aam"][sid]]
    deltas = sorted(((state["aam"][s]["overall"] - state["legacy"][s]["overall"], s)
                     for s in both), key=lambda t: -abs(t[0]))
    lines += ["## Largest per-image overall-score shifts (aam - legacy)", ""]
    lines += [f"- {s}: {d:+.2f}" for d, s in deltas[:10]]
    state["summary"] = result
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    items = load_items()
    print(f"{len(items)} labeled image creatives with media on disk")
    state = {}
    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding="utf-8") as f:
            state = json.load(f)
        state.pop("summary", None)
    score_pass(items, "legacy", state)
    score_pass(items, "aam", state)
    analyze(items, state)


if __name__ == "__main__":
    main()
