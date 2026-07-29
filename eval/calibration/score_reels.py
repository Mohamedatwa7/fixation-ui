"""Reels calibration phase 1: score brand reels through the deployed video
pipeline and measure top-vs-bottom discrimination.

Selects up to PER_STRATUM (20) reels per stratum from the instagram-video
queues (freshest videoUrls first — they expire), submits each to
/api/analyze/video-url/submit, polls /api/job/<id>, and saves results to
data/results-video/<pid>.json (resumable). Ends with AUC/Spearman over all
scored reels.

    python eval/calibration/score_reels.py
"""

import json
import os
import sys
import time

from calibrate import (DATA_DIR, DATASET_PATH, load_env, require, get_requests,
                       spearman, auc)

RESULTS_VIDEO = os.path.join(DATA_DIR, "results-video")
PER_STRATUM = int(os.environ.get("PER_STRATUM", "20"))
POLL_S = 20
JOB_TIMEOUT_S = 15 * 60


def submit_and_wait(requests, base, video_url):
    r = requests.post(f"{base}/api/analyze/video-url/submit",
                      data={"url": video_url}, timeout=120)
    r.raise_for_status()
    job_id = r.json()["job_id"]
    deadline = time.time() + JOB_TIMEOUT_S
    not_found = 0
    while time.time() < deadline:
        time.sleep(POLL_S)
        s = requests.get(f"{base}/api/job/{job_id}", timeout=60).json()
        status = s.get("status")
        if status == "done":
            return s["result"]
        if status == "error":
            return {"error": s.get("error", "?")[:300]}
        if status == "not_found":
            # JOBS is per-container; a cold-start swap loses the job
            not_found += 1
            if not_found >= 3:
                return {"error": "job lost (container recycled)"}
    return {"error": "timeout"}


def main():
    load_env()
    requests = get_requests()
    base = require("F1X8_API_URL").rstrip("/")
    with open(DATASET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    os.makedirs(RESULTS_VIDEO, exist_ok=True)

    todo = []
    for stratum in ("top", "bottom"):
        n = 0
        for pid in ds["candidates"].get(f"instagram-video|{stratum}", []):
            if n >= PER_STRATUM:
                break
            e = posts[pid]
            if not e.get("media_url"):
                continue
            if os.path.exists(os.path.join(RESULTS_VIDEO, pid + ".json")):
                n += 1  # already scored counts toward the stratum quota
                continue
            todo.append(e)
            n += 1
    print(f"scoring {len(todo)} reels via {base} (sequential; ~3-6 min each)")

    for i, e in enumerate(todo):
        t0 = time.time()
        result = submit_and_wait(requests, base, e["media_url"])
        result.pop("heatmap", None)
        with open(os.path.join(RESULTS_VIDEO, e["id"] + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        tag = f"score={result.get('score')}" if "score" in result \
            else "ERROR: " + result.get("error", "?")[:80]
        print(f"  [{i + 1}/{len(todo)}] {e['id'][:8]} {e['stratum']:<6} {tag} "
              f"({time.time() - t0:.0f}s)", flush=True)

    rows = []
    for fn in os.listdir(RESULTS_VIDEO):
        pid = fn[:-5]
        if pid not in posts:
            continue
        with open(os.path.join(RESULTS_VIDEO, fn), encoding="utf-8") as f:
            r = json.load(f)
        if "score" in r:
            rows.append({**posts[pid], "score": r["score"]})
    if len(rows) < 10:
        sys.exit(f"only {len(rows)} scored reels -- not enough for stats")
    top = [r["score"] for r in rows if r["stratum"] == "top"]
    bot = [r["score"] for r in rows if r["stratum"] == "bottom"]
    rho = spearman([r["score"] for r in rows], [r["percentile"] for r in rows])
    print(f"\nREELS: n={len(rows)} ({len(top)} top / {len(bot)} bottom) "
          f"AUC {auc(top, bot):.3f} | Spearman {rho:.2f}")


if __name__ == "__main__":
    main()
