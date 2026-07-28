"""Project median-of-3 ensemble reliability from an existing single-call run.

Uses the 8 test-retest originals per image in a run's results.json: every
C(8,3) subsample's per-KPI median approximates one ensemble judgment, so the
std across subsamples estimates the ensemble's test-retest std. Compare with
the single-call std in REPORT.md.

Usage: python eval/ensemble_projection.py --run eval/runs/<ts>
"""
import argparse
import itertools
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_reliability as jr


def main(run_dir):
    with open(os.path.join(run_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(run_dir, "results.json")) as f:
        results = json.load(f)

    by_image = {}
    for cid, meta in manifest.items():
        if meta["variant"] != "original":
            continue
        res = results.get(cid, {})
        j = jr.parse_engagement(res.get("text")) if res.get("ok") else None
        if j is not None:
            by_image.setdefault(meta["image"], []).append(j)

    print(f"{'image':<18} {'kpi':<22} {'single std':>10} {'median3 std':>11} {'reduction':>9}")
    for img, runs in sorted(by_image.items()):
        for k in jr.JUDGED_KPIS + ["displayed(sim)"]:
            if k == "displayed(sim)":
                vals = [jr.simulated_score(j) for j in runs]
            else:
                vals = [float((j.get(k) or {}).get("score", 5)) for j in runs]
            single = statistics.pstdev(vals)
            meds = [statistics.median(c) for c in itertools.combinations(vals, 3)]
            ens = statistics.pstdev(meds)
            red = (1 - ens / single) * 100 if single else 0.0
            print(f"{img:<18} {k:<22} {single:>10.3f} {ens:>11.3f} {red:>8.0f}%")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    main(p.parse_args().run)
