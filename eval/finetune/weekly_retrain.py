"""Weekly ranker retrain loop.

Each week new brand posts mature past the 14-day label filter with live CDN
urls, so the training pool grows. This script runs the full cycle:

  export -> build (60/40 bands, video queues) -> refresh urls (scrape new
  candidates) -> download -> prep pairs -> train (promote adapter only if
  holdout AUC >= best so far) -> record best.

Run manually or via the scheduled task (see run_weekly.cmd):

    python eval/finetune/weekly_retrain.py
"""

import json
import os
import subprocess
import sys

FT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(FT_DIR, "..", ".."))
BEST_PATH = os.path.join(FT_DIR, "data", "best_auc.json")


def run(desc, args, extra_env=None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(extra_env or {})}
    print(f"\n=== {desc}: {' '.join(args)}", flush=True)
    r = subprocess.run([sys.executable] + args, cwd=REPO, env=env)
    if r.returncode != 0:
        sys.exit(f"step failed ({desc}) -- aborting weekly cycle")


def main():
    best = 0.0
    if os.path.exists(BEST_PATH):
        with open(BEST_PATH, encoding="utf-8") as f:
            best = json.load(f)["holdout_auc"]
    print(f"weekly retrain cycle; best holdout AUC so far: {best}")

    cal = ["eval/calibration/calibrate.py"]
    band_env = {"STRATA_TOP": "60", "STRATA_BOTTOM": "40", "INCLUDE_VIDEO": "1"}
    run("export", cal + ["export"])
    run("build", cal + ["build"], band_env)
    run("refresh urls", ["eval/calibration/refresh_urls.py"],
        {"PER_QUEUE": "60", "TARGET_IMAGES": "999"})
    run("download", cal + ["download"], {"SAMPLE_CAP": "1000"})
    run("prep pairs", ["eval/finetune/prep_pairs.py"])
    run("train", ["-m", "modal", "run", "eval/finetune/train_ranker_modal.py"],
        {"PROMOTE_MIN_AUC": str(best)})

    with open(os.path.join(FT_DIR, "data", "train_metrics.json"), encoding="utf-8") as f:
        metrics = json.load(f)
    print(f"\ncycle done: holdout AUC {metrics['holdout_auc']} "
          f"(best {best}) promoted={metrics.get('promoted')}")
    if metrics.get("promoted") and metrics["holdout_auc"] > best:
        with open(BEST_PATH, "w", encoding="utf-8") as f:
            json.dump({"holdout_auc": metrics["holdout_auc"]}, f)
        print(f"new best recorded: {metrics['holdout_auc']}")


if __name__ == "__main__":
    main()
