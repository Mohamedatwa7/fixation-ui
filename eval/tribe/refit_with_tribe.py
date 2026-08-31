"""Does TRIBE v2 add predictive power for realized engagement?

Compares, per media kind and overall, stratified 5-fold CV AUC of:
  A) baseline: the pipeline's existing score alone
     (organic_engagement when present, else engagement_potential)
  B) baseline + TRIBE v2 network features (L2 logistic regression, numpy-only)

Labels follow the calibration convention: top stratum percentile >= 60 -> 1,
bottom <= 40 -> 0, middle dropped.

Usage: python eval/tribe/refit_with_tribe.py [--image-results results-anchored-v2]
"""
import argparse
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "calibration", "data")


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    diff = pos[:, None] - neg[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum()) / (len(pos) * len(neg)))


def logistic_fit(X, y, lam=1.0, iters=800, lr=0.1):
    """Full-batch gradient descent, L2-regularized (bias unpenalized)."""
    Xb = np.hstack([np.ones((len(X), 1)), X])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-Xb @ w))
        g = Xb.T @ (p - y) / len(y)
        g[1:] += lam * w[1:] / len(y)
        w -= lr * g
    return w


def logistic_score(w, X):
    Xb = np.hstack([np.ones((len(X), 1)), X])
    return Xb @ w


def cv_auc(X, y, folds=5, seed=7):
    rng = np.random.default_rng(seed)
    idx_pos = rng.permutation(np.where(y == 1)[0])
    idx_neg = rng.permutation(np.where(y == 0)[0])
    fold_of = np.zeros(len(y), dtype=int)
    for k, i in enumerate(idx_pos):
        fold_of[i] = k % folds
    for k, i in enumerate(idx_neg):
        fold_of[i] = k % folds
    aucs = []
    for f in range(folds):
        tr, te = fold_of != f, fold_of == f
        if y[te].min() == y[te].max():
            continue
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        w = logistic_fit((X[tr] - mu) / sd, y[tr])
        aucs.append(auc(y[te], logistic_score(w, (X[te] - mu) / sd)))
    return float(np.mean(aucs)), len(aucs)


def load_baseline(pid, kind, image_dir):
    d = "results-video" if kind == "video" else image_dir
    p = os.path.join(DATA, d, f"{pid}.json")
    if not os.path.exists(p):
        return None
    r = json.load(open(p, encoding="utf-8"))
    v = r.get("organic_engagement")
    return v if isinstance(v, (int, float)) else r.get("engagement_potential")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-results", default="results-anchored-v2")
    args = ap.parse_args()

    posts = {p["id"]: p for p in
             json.load(open(os.path.join(DATA, "dataset.json"), encoding="utf-8"))["posts"]}
    feats = [r for r in json.load(open(os.path.join(HERE, "features.json"), encoding="utf-8"))
             if r.get("ok")]

    feat_keys = sorted(k for k in feats[0]["features"] if k != "n_timesteps")
    rows = []
    for r in feats:
        p = posts.get(r["id"])
        if not p or p.get("percentile") is None:
            continue
        pct = p["percentile"]
        if 40 < pct < 60:
            continue
        base = load_baseline(r["id"], r["kind"], args.image_results)
        if base is None:
            continue
        rows.append({
            "kind": r["kind"], "y": 1 if pct >= 60 else 0, "base": base,
            "x": [r["features"][k] for k in feat_keys],
        })

    print(f"n={len(rows)} labeled creatives with baseline + TRIBE features "
          f"({sum(1 for r in rows if r['kind'] == 'image')} image / "
          f"{sum(1 for r in rows if r['kind'] == 'video')} video)")
    print(f"{len(feat_keys)} TRIBE features: {feat_keys[:6]}...\n")

    for kind in ("image", "video", "all"):
        sub = [r for r in rows if kind == "all" or r["kind"] == kind]
        if len(sub) < 10:
            print(f"[{kind}] n={len(sub)} — too few, skipping")
            continue
        y = np.array([r["y"] for r in sub])
        base = np.array([[r["base"]] for r in sub], dtype=float)
        X = np.hstack([base, np.array([r["x"] for r in sub], dtype=float)])
        raw_auc = auc(y, base[:, 0])
        a_cv, _ = cv_auc(base, y)
        b_cv, nf = cv_auc(X, y)
        print(f"[{kind}] n={len(sub)} pos={int(y.sum())}")
        print(f"  baseline score, raw AUC:        {raw_auc:.3f}")
        print(f"  baseline alone, {nf}-fold CV AUC: {a_cv:.3f}")
        print(f"  baseline + TRIBE, CV AUC:       {b_cv:.3f}   (delta {b_cv - a_cv:+.3f})\n")


if __name__ == "__main__":
    main()
