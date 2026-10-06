"""Build outcome-calibrated KPI benchmarks from Alibaba CreativeRanking.

Replaces the MAdVerse-era percentile yardstick ("better than X% of real ads")
with one calibrated against real click outcomes ("in the range where
high-CTR creatives live"). Dataset: 1.7M creatives / 500k products / 215M
impressions (Alimama, WWW 2021), rows = (product, image, day, shows, clicks).

Phases (each resumable, run in order):

    python build_benchmark.py sample    # aggregate lists -> stratified sample
    python build_benchmark.py extract   # pull sampled images out of images.zip
    python build_benchmark.py score     # AAM saliency + KPI raw values (GPU, hours)
    python build_benchmark.py build     # percentile JSONs + KPI-vs-CTR validation

Outputs in data/:
    sample.json      {image: {product, shows, clicks, ctr_s, pctl_in_product, stratum}}
    scores.jsonl     one line per scored image (raw KPI values)
    benchmark_creativeranking_highctr.json   lookup-compatible percentiles
    REPORT.md        KPI-vs-outcome correlations at n=tens-of-thousands
"""

import json
import os
import random
import sys
import zipfile
from collections import defaultdict

CR_DIR = r"D:\datasets\CreativeRanking"
LIST_DIR = os.path.join(CR_DIR, "list_extracted", "list")
IMAGES_ZIP = os.path.join(CR_DIR, "images.zip")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
IMG_DIR = os.path.join(OUT_DIR, "images")
SAMPLE_PATH = os.path.join(OUT_DIR, "sample.json")
SCORES_PATH = os.path.join(OUT_DIR, "scores.jsonl")
BENCH_PATH = os.path.join(OUT_DIR, "benchmark_creativeranking_highctr.json")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT.md")

MIN_SHOWS = 100          # below this CTR is noise
MIN_CREATIVES = 3        # need competition within a product for ranks
N_HIGH = 20000           # top-quartile-within-product creatives (benchmark pool)
N_RAND = 20000           # random eligible creatives (validation pool)
SMOOTH_A, SMOOTH_B = 1.0, 200.0   # Bayesian CTR smoothing toward pool mean
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

random.seed(48)


def _aggregate():
    """Sum shows/clicks per image across days and splits."""
    agg = {}
    for name in ("train_data_list.txt", "val_data_list.txt", "test_data_list.txt"):
        path = os.path.join(LIST_DIR, name)
        with open(path, encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) != 5:
                    continue
                prod, img, _, shows, clicks = p
                rec = agg.get(img)
                if rec is None:
                    agg[img] = rec = [prod, 0, 0]
                rec[1] += int(shows)
                rec[2] += int(clicks)
        print(f"aggregated {name}: {len(agg)} images so far", flush=True)
    return agg


def cmd_sample():
    os.makedirs(OUT_DIR, exist_ok=True)
    agg = _aggregate()
    pool_ctr = (sum(r[2] for r in agg.values())
                / max(1, sum(r[1] for r in agg.values())))
    by_prod = defaultdict(list)
    for img, (prod, shows, clicks) in agg.items():
        if shows >= MIN_SHOWS:
            ctr_s = (clicks + SMOOTH_A * pool_ctr * SMOOTH_B) / (shows + SMOOTH_B)
            by_prod[prod].append((img, shows, clicks, ctr_s))
    sample = {}
    eligible = []
    for prod, rows in by_prod.items():
        if len(rows) < MIN_CREATIVES:
            continue
        rows.sort(key=lambda r: r[3])
        n = len(rows)
        for rank, (img, shows, clicks, ctr_s) in enumerate(rows):
            pctl = 100.0 * (rank + 0.5) / n
            eligible.append((img, prod, shows, clicks, ctr_s, pctl))
    print(f"eligible creatives (>= {MIN_SHOWS} shows, product has >= "
          f"{MIN_CREATIVES} creatives): {len(eligible)}")
    high = [e for e in eligible if e[5] >= 75.0]
    random.shuffle(high)
    random.shuffle(eligible)
    for img, prod, shows, clicks, ctr_s, pctl in high[:N_HIGH]:
        sample[img] = {"product": prod, "shows": shows, "clicks": clicks,
                       "ctr_s": round(ctr_s, 6), "pctl_in_product": round(pctl, 1),
                       "stratum": "high"}
    taken = 0
    for img, prod, shows, clicks, ctr_s, pctl in eligible:
        if taken >= N_RAND:
            break
        if img in sample:
            continue
        sample[img] = {"product": prod, "shows": shows, "clicks": clicks,
                       "ctr_s": round(ctr_s, 6), "pctl_in_product": round(pctl, 1),
                       "stratum": "random"}
        taken += 1
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump(sample, f)
    strata = defaultdict(int)
    for v in sample.values():
        strata[v["stratum"]] += 1
    print(f"sample written: {dict(strata)} -> {SAMPLE_PATH}")


def cmd_extract():
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        sample = json.load(f)
    os.makedirs(IMG_DIR, exist_ok=True)
    want = {img for img in sample
            if not os.path.exists(os.path.join(IMG_DIR, img))}
    print(f"extracting {len(want)} of {len(sample)} images from images.zip")
    if not want:
        return
    with zipfile.ZipFile(IMAGES_ZIP) as z:
        names = z.namelist()
        by_base = {}
        for n in names:
            base = n.rsplit("/", 1)[-1]
            if base in want:
                by_base[base] = n
        print(f"matched {len(by_base)} members in archive")
        done = 0
        for base, member in by_base.items():
            with z.open(member) as src, \
                    open(os.path.join(IMG_DIR, base), "wb") as dst:
                dst.write(src.read())
            done += 1
            if done % 2000 == 0:
                print(f"  {done}/{len(by_base)}", flush=True)
    print("extract complete")


def cmd_score():
    sys.path.insert(0, os.path.join(REPO, "backend_scripts"))
    import cv2
    from analyze_image import compute_saliency_map
    from image_kpis import (visual_hierarchy, composition_balance,
                            white_space_ratio, color_contrast, visual_complexity)
    os.environ.setdefault("F1X8_SALIENCY", "aam")

    with open(SAMPLE_PATH, encoding="utf-8") as f:
        sample = json.load(f)
    done = set()
    if os.path.exists(SCORES_PATH):
        with open(SCORES_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["image"])
                except Exception:
                    pass
    todo = [img for img in sample
            if img not in done and os.path.exists(os.path.join(IMG_DIR, img))]
    print(f"{len(todo)} to score ({len(done)} already done)")
    out = open(SCORES_PATH, "a", encoding="utf-8")
    import time
    t0 = time.time()
    for i, img in enumerate(todo, 1):
        path = os.path.join(IMG_DIR, img)
        try:
            bgr = cv2.imread(path)
            if bgr is None:
                raise ValueError("unreadable image")
            sal, _ = compute_saliency_map(path)
            row = {"image": img}
            for key, fn in (("hierarchy", visual_hierarchy),
                            ("composition", composition_balance),
                            ("white_space", white_space_ratio),
                            ("contrast", color_contrast),
                            ("complexity", visual_complexity)):
                try:
                    k = fn(bgr, sal) if key in ("hierarchy", "composition",
                                                "contrast") else fn(bgr)
                    row[key] = {"score": k.get("score"), "raw": k.get("raw_value")}
                except Exception as e:
                    row[key] = {"error": str(e)}
            out.write(json.dumps(row) + "\n")
        except Exception as e:
            out.write(json.dumps({"image": img, "error": str(e)}) + "\n")
        if i % 200 == 0:
            rate = i / (time.time() - t0)
            eta_h = (len(todo) - i) / rate / 3600
            print(f"  {i}/{len(todo)}  {rate:.1f} img/s  ETA {eta_h:.1f}h", flush=True)
            out.flush()
    out.close()
    print("scoring complete")


def _pctl_block(vals):
    vals = sorted(vals)
    n = len(vals)
    pcts = [round(vals[min(n - 1, int(p / 100.0 * n))], 4) for p in range(101)]
    return {"n": n, "min": round(vals[0], 4), "max": round(vals[-1], 4),
            "median": pcts[50], "mean": round(sum(vals) / n, 4),
            "percentiles": pcts}


def cmd_build():
    sys.path.insert(0, os.path.join(REPO, "eval", "calibration"))
    from aam_ab import spearman, auc

    with open(SAMPLE_PATH, encoding="utf-8") as f:
        sample = json.load(f)
    rows = []
    with open(SCORES_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "error" in r or r["image"] not in sample:
                continue
            rows.append(r)
    print(f"{len(rows)} scored rows")

    # Benchmark distributions from the high-CTR stratum only.
    bench_key = {"hierarchy": "hierarchy_gini", "composition": "composition_dist",
                 "white_space": "white_space_ratio", "contrast": "contrast_ratio",
                 "complexity": "edge_density"}
    bench = {}
    for kpi, key in bench_key.items():
        vals = [r[kpi]["raw"] for r in rows
                if sample[r["image"]]["stratum"] == "high"
                and isinstance(r[kpi].get("raw"), (int, float))]
        if len(vals) >= 1000:
            bench[key] = _pctl_block(vals)
    bench["n_images"] = bench[next(iter(bench))]["n"] if bench else 0
    bench["source"] = ("Alibaba CreativeRanking top-quartile-within-product "
                       "creatives (real CTR outcomes), scored with AAM saliency")
    with open(BENCH_PATH, "w", encoding="utf-8") as f:
        json.dump(bench, f)
    print(f"benchmark written: {sorted(bench_key.values())} -> {BENCH_PATH}")

    # Validation: KPI scores vs within-product CTR percentile on the random stratum.
    lines = ["# CreativeRanking KPI validation", "",
             "KPI score vs within-product CTR percentile, random stratum "
             "(creatives with >= 100 shows, products with >= 3 creatives).", ""]
    rnd = [r for r in rows if sample[r["image"]]["stratum"] == "random"]
    ys = [sample[r["image"]]["pctl_in_product"] for r in rnd]
    med = sorted(ys)[len(ys) // 2]
    for kpi in bench_key:
        pairs = [(r[kpi]["score"], y) for r, y in zip(rnd, ys)
                 if isinstance(r[kpi].get("score"), (int, float))]
        xs = [p[0] for p in pairs]
        yy = [p[1] for p in pairs]
        rho = spearman(xs, yy)
        top = [x for x, y in pairs if y >= med]
        bot = [x for x, y in pairs if y < med]
        lines.append(f"- {kpi}: Spearman {rho:+.4f}, top-vs-bottom AUC "
                     f"{auc(top, bot):.4f}  (n={len(pairs)})")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sample"
    {"sample": cmd_sample, "extract": cmd_extract,
     "score": cmd_score, "build": cmd_build}[cmd]()
