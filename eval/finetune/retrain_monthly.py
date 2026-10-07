"""Monthly ranker retrain: refresh labels -> fine-tune -> promote if better.

The label stream grows on its own (scraped posts mature past the 14-day
engagement filter), so the ranker should be retrained on a cadence. This
orchestrates the loop with two safety properties:

1. FROZEN HOLDOUT: the 82 holdout creatives in data/manifest.json never
   change and never enter training — every retrain is measured on the same
   yardstick as the 0.851/0.921 results. New matured creatives only ever
   join the train split.
2. PROMOTE GATE: the new adapter replaces out_samsung/production only if
   its frozen-holdout AUC beats the incumbent's recorded best. Otherwise it
   is parked in out_samsung/candidate_<date> for inspection.

    D:\\F1X8\\.venv-train\\Scripts\\python.exe eval/finetune/retrain_monthly.py
        [--skip-refresh]   # train on current manifest without Supabase pull

Schedule (Windows): register_retrain_task.ps1 creates a monthly scheduled
task. The run is GPU-heavy (~1h) — it shares the 5090 with the serving
sidecar, so schedule off-hours.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date

FT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(FT_DIR))
CAL_DIR = os.path.join(REPO, "eval", "calibration")
MEDIA_DIR = os.path.join(CAL_DIR, "data", "media")
MANIFEST = os.path.join(FT_DIR, "data", "manifest.json")
OUT_ROOT = os.path.join(FT_DIR, "out_samsung")
PROD_DIR = os.path.join(OUT_ROOT, "production")
PY = sys.executable


def refresh_labels():
    """Pull fresh outcomes and add newly matured creatives to the train split."""
    cal_py = os.path.join(CAL_DIR, "calibrate.py")
    for step in ("export", "build", "download"):
        print(f"[refresh] calibrate.py {step}")
        r = subprocess.run([PY, cal_py, step], cwd=REPO, capture_output=True,
                           text=True, timeout=3600)
        if r.returncode != 0:
            print(r.stdout[-500:], r.stderr[-500:])
            raise RuntimeError(f"calibrate {step} failed — aborting refresh")
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    known = {it["id"] for split in manifest.values() for it in split}
    with open(os.path.join(CAL_DIR, "data", "dataset.json"), encoding="utf-8") as f:
        d = json.load(f)
    added = 0
    for p in d["posts"]:
        if (isinstance(p, dict) and p.get("kind") == "image"
                and p.get("id") not in known
                and p.get("percentile") is not None
                and os.path.exists(os.path.join(MEDIA_DIR, f"{p['id']}.jpg"))):
            manifest["train"].append({
                "id": p["id"],
                "image": os.path.join(MEDIA_DIR, f"{p['id']}.jpg"),
                "stratum": "top" if p["percentile"] >= 75 else
                           "bottom" if p["percentile"] <= 25 else "mid",
                "percentile": p["percentile"],
                "platform": p.get("platform"),
            })
            added += 1
    if added:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
    print(f"[refresh] +{added} new train creatives "
          f"(train={len(manifest['train'])}, holdout={len(manifest['holdout'])} frozen)")


def incumbent_auc():
    p = os.path.join(PROD_DIR, "RESULT.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return float(json.load(f).get("best_holdout_auc", 0))
    return 0.851  # v1 baseline if no production record yet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-refresh", action="store_true")
    args = ap.parse_args()
    if not args.skip_refresh:
        try:
            refresh_labels()
        except Exception as e:
            print(f"[refresh] FAILED ({e}); training on current manifest")

    tag = f"retrain_{date.today().isoformat()}"
    # Reuse the validated recipe: pretrained CR adapter, gentle LR.
    sys.path.insert(0, FT_DIR)
    import finetune_samsung as ft
    ft.VARIANTS[tag] = {"pretrained": True, "lr": 5e-6}
    best = ft.run_variant(tag, ft.VARIANTS[tag])

    inc = incumbent_auc()
    cand = os.path.join(OUT_ROOT, tag)
    if best > inc:
        if os.path.isdir(PROD_DIR):
            shutil.rmtree(PROD_DIR)
        shutil.copytree(cand, PROD_DIR)
        print(f"[promote] {best:.3f} > incumbent {inc:.3f} -> promoted to production/")
        print("[promote] NOTE: upload production/ to the fixation-ranker volume "
              "and restart the local sidecar to serve it.")
    else:
        print(f"[promote] {best:.3f} <= incumbent {inc:.3f} -> parked in {tag}/")


if __name__ == "__main__":
    main()
