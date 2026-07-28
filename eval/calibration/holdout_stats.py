"""Split-aware calibration stats: anchor-design set vs untouched holdout.

The design split's judge results were used to write the prompt anchors, so
its numbers are in-sample; the holdout split is the honest generalization
measure for the anchored judge.

    python eval/calibration/holdout_stats.py
"""

import json
import os

from calibrate import DATA_DIR, DATASET_PATH, RESULTS_DIR, spearman, auc, bootstrap_ci


def main():
    with open(DATASET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    pre = os.path.join(DATA_DIR, "results-preanchor")
    design = {fn[:-5] for fn in os.listdir(pre)} if os.path.isdir(pre) else set()

    splits = {"design (in-sample)": [], "holdout (out-of-sample)": []}
    for pid in ds["sample"]:
        path = os.path.join(RESULTS_DIR, pid + ".json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        if "score" not in r:
            continue
        e = posts[pid]
        key = "design (in-sample)" if pid in design else "holdout (out-of-sample)"
        splits[key].append({**e, "score": r["score"],
                            "kpis": {k: v.get("score") for k, v in (r.get("kpis") or {}).items()}})

    for name, rows in splits.items():
        if len(rows) < 10:
            print(f"{name}: only {len(rows)} scored -- skipping")
            continue
        top = [r["score"] for r in rows if r["stratum"] == "top"]
        bot = [r["score"] for r in rows if r["stratum"] == "bottom"]
        pairs = [(r["score"], r["percentile"]) for r in rows]
        rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
        lo, hi = bootstrap_ci(pairs, spearman)
        print(f"\n== {name}: n={len(rows)} ({len(top)} top / {len(bot)} bottom)")
        print(f"   AUC {auc(top, bot):.3f} | Spearman {rho:.2f} (CI {lo:.2f}..{hi:.2f})")
        kpi_ids = sorted({k for r in rows for k in r["kpis"]})
        for kid in kpi_ids:
            sub = [r for r in rows if r["kpis"].get(kid) is not None]
            if len(sub) < 10:
                continue
            krho = spearman([r["kpis"][kid] for r in sub], [r["percentile"] for r in sub])
            print(f"   {kid:<18} n={len(sub):<3} rho {krho:+.2f}")


if __name__ == "__main__":
    main()
