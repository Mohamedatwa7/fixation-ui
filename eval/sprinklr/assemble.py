"""Sprinklr chain B: merge media+accounts into the dataset, re-cohort
account-aware, freeze the multi-platform holdout, build training pairs.

Account-aware relabeling: percentiles recomputed within platform x ACCOUNT
x quarter cohorts (merge-up to platform x account, then platform). This is
what makes "how does this perform on account X" answerable, and it tightens
the paid-robustness story (an account's boosted era ranks against itself).

Holdout: ~400 creatives stratified by platform x stratum, frozen in
data/holdout_ids.json — never trained on, ever. Pairs: within-cohort,
percentile gap >= 30, capped per cohort for diversity.

    python eval/sprinklr/assemble.py
"""

import json
import os
import random
from collections import defaultdict, Counter

SPR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SPR_DIR, "data")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
OUT_DATASET = os.path.join(DATA_DIR, "dataset.json")
OUT_HOLDOUT = os.path.join(DATA_DIR, "holdout_ids.json")
OUT_PAIRS = os.path.join(DATA_DIR, "pairs.json")

MIN_COHORT = 8
MIN_GAP = 30.0
HOLDOUT_N = 400
MAX_PAIRS_PER_COHORT = 400

random.seed(48)


def main():
    with open(os.path.join(DATA_DIR, "labels.json"), encoding="utf-8") as f:
        posts = json.load(f)
    with open(os.path.join(DATA_DIR, "media_meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    rows = []
    for p in posts:
        m = meta.get(p["url"]) or {}
        f = m.get("file")
        if not f or not os.path.exists(os.path.join(MEDIA_DIR, f)):
            continue
        rows.append({**p,
                     "account": m.get("account") or "(unknown)",
                     "caption_full": m.get("caption_full") or p.get("caption", ""),
                     "image": os.path.join(MEDIA_DIR, f),
                     "id": f.split(".")[0]})
    print(f"{len(rows)} creatives with media + labels")
    print("by platform:", dict(Counter(r['platform'] for r in rows)))
    print("accounts:", len({(r['platform'], r['account']) for r in rows}))

    # account-aware cohorts with merge-up
    def key3(r): return (r["platform"], r["account"], r["quarter"])
    def key2(r): return (r["platform"], r["account"])
    def key1(r): return (r["platform"],)
    c3, c2 = Counter(map(key3, rows)), Counter(map(key2, rows))
    groups = defaultdict(list)
    for r in rows:
        k = key3(r) if c3[key3(r)] >= MIN_COHORT else \
            key2(r) if c2[key2(r)] >= MIN_COHORT else key1(r)
        r["cohort"] = " / ".join(map(str, k))
        groups[r["cohort"]].append(r)
    for grp in groups.values():
        grp.sort(key=lambda r: r["er"])
        n = len(grp)
        for i, r in enumerate(grp):
            r["percentile"] = round(100.0 * (i + 0.5) / n, 1)
            r["stratum"] = ("top" if r["percentile"] >= 75 else
                            "bottom" if r["percentile"] <= 25 else "mid")

    # frozen holdout: stratified by platform x stratum (top/bottom only —
    # the eval metric is top-vs-bottom discrimination)
    if os.path.exists(OUT_HOLDOUT):
        with open(OUT_HOLDOUT, encoding="utf-8") as f:
            holdout_ids = set(json.load(f))
        print(f"holdout already frozen: {len(holdout_ids)} ids (unchanged)")
    else:
        buckets = defaultdict(list)
        for r in rows:
            if r["stratum"] in ("top", "bottom"):
                buckets[(r["platform"], r["stratum"])].append(r["id"])
        per_bucket = max(10, HOLDOUT_N // max(1, len(buckets)))
        holdout_ids = set()
        for ids in buckets.values():
            random.shuffle(ids)
            holdout_ids.update(ids[:per_bucket])
        with open(OUT_HOLDOUT, "w", encoding="utf-8") as f:
            json.dump(sorted(holdout_ids), f)
        print(f"holdout FROZEN: {len(holdout_ids)} creatives")

    for r in rows:
        r["split"] = "holdout" if r["id"] in holdout_ids else "train"
    with open(OUT_DATASET, "w", encoding="utf-8") as f:
        json.dump(rows, f)

    # training pairs: within cohort, big gaps, train split only
    pairs = []
    for cohort, grp in groups.items():
        tr = [r for r in grp if r["split"] == "train"]
        cand = [(a, b) for a in tr for b in tr
                if a["percentile"] - b["percentile"] >= MIN_GAP]
        random.shuffle(cand)
        pairs.extend({"top": a["id"], "bottom": b["id"], "cohort": cohort}
                     for a, b in cand[:MAX_PAIRS_PER_COHORT])
    random.shuffle(pairs)
    with open(OUT_PAIRS, "w", encoding="utf-8") as f:
        json.dump(pairs, f)
    hold_n = Counter(r["platform"] for r in rows if r["split"] == "holdout")
    print(f"pairs: {len(pairs)} | holdout by platform: {dict(hold_n)}")


if __name__ == "__main__":
    main()
