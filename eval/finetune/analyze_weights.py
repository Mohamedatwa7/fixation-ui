"""Holdout-validated KPI weight analysis for social-organic scoring.

Run 3 showed the judged KPIs carry very different amounts of organic-
engagement signal (brand_strength rho 0.45 vs attention_capture -0.19).
This script asks: if the funnel weights were tuned for organic social,
how much better would the displayed score rank real engagement?

Method: logistic Bradley-Terry on (top - bottom) KPI-difference features,
fitted on the anchor-design split only, evaluated on the holdout split.
Compares holdout AUC of (a) the deployed overall score, (b) brand_strength
alone, (c) the fitted weights. Analysis artifact only — deployed funnel
weights are NOT changed by this script.

    python eval/finetune/analyze_weights.py  ->  eval/finetune/data/weights_report.json
"""

import json
import math
import os
import random

FT_DIR = os.path.dirname(os.path.abspath(__file__))
CAL_DATA = os.path.normpath(os.path.join(FT_DIR, "..", "calibration", "data"))
RESULTS = os.path.join(CAL_DATA, "results")
OUT = os.path.join(FT_DIR, "data", "weights_report.json")

KPI_ORDER = ["attention_capture", "emotional_pull", "brand_strength",
             "distinctiveness", "persuasive_power", "trust_credibility",
             "message_clarity"]


def load_rows():
    with open(os.path.join(FT_DIR, "data", "manifest.json"), encoding="utf-8") as f:
        splits = json.load(f)
    out = {}
    for name, items in splits.items():
        rows = []
        for it in items:
            path = os.path.join(RESULTS, it["id"] + ".json")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                r = json.load(f)
            if "score" not in r:
                continue
            kpis = {k: v.get("score") for k, v in (r.get("kpis") or {}).items()}
            feats = [kpis.get(k) if kpis.get(k) is not None else 5.0
                     for k in KPI_ORDER]
            rows.append({**it, "overall": r["score"], "feats": feats,
                         "brand": kpis.get("brand_strength", 5.0)})
        out[name] = rows
    return out


def auc(rows, key):
    top = [key(r) for r in rows if r["stratum"] == "top"]
    bot = [key(r) for r in rows if r["stratum"] == "bottom"]
    if not top or not bot:
        return float("nan")
    wins = sum(1 if t > b else 0.5 if t == b else 0 for t in top for b in bot)
    return wins / (len(top) * len(bot))


def fit_bt(rows, epochs=400, lr=0.05, l2=1e-3, seed=13):
    """Logistic Bradley-Terry on top-bottom KPI diffs; returns weight vector."""
    tops = [r for r in rows if r["stratum"] == "top"]
    bots = [r for r in rows if r["stratum"] == "bottom"]
    pairs = [(t["feats"], b["feats"]) for t in tops for b in bots]
    rng = random.Random(seed)
    w = [0.0] * len(KPI_ORDER)
    for _ in range(epochs):
        rng.shuffle(pairs)
        for ft, fb in pairs:
            d = [a - b for a, b in zip(ft, fb)]
            z = sum(wi * di for wi, di in zip(w, d))
            g = 1.0 / (1.0 + math.exp(-z)) - 1.0  # d(loss)/dz for label=1
            for i in range(len(w)):
                w[i] -= lr * (g * d[i] + l2 * w[i]) / len(pairs)
    return w


def main():
    splits = load_rows()
    train, holdout = splits["train"], splits["holdout"]
    print(f"train rows {len(train)}, holdout rows {len(holdout)}")
    w = fit_bt(train)
    wnamed = {k: round(v, 3) for k, v in zip(KPI_ORDER, w)}

    def fitted(r):
        return sum(wi * fi for wi, fi in zip(w, r["feats"]))

    report = {
        "fitted_weights": wnamed,
        "train_auc": {"deployed_score": round(auc(train, lambda r: r["overall"]), 3),
                      "brand_strength_only": round(auc(train, lambda r: r["brand"]), 3),
                      "fitted": round(auc(train, fitted), 3)},
        "holdout_auc": {"deployed_score": round(auc(holdout, lambda r: r["overall"]), 3),
                        "brand_strength_only": round(auc(holdout, lambda r: r["brand"]), 3),
                        "fitted": round(auc(holdout, fitted), 3)},
        "n": {"train": len(train), "holdout": len(holdout)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
