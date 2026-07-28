"""Refresh expired Instagram CDN links for the calibration sample.

Instagram media_urls are signed and expire within days, so the Supabase rows
for aged (label-mature) posts are mostly dead. This step scrapes fresh
displayUrls for the head of each candidate queue via apify/instagram-scraper
(`directUrls` mode), accumulating results in data/refresh_tried.json across
passes (many "image" candidates turn out to be reels — the Supabase
media_type is wrong for them — so several passes may be needed to fill the
top stratum). After each pass it patches dataset.json: fresh media_urls
applied, queues pruned to confirmed-image refreshed posts.

    python refresh_urls.py                      # scrape next PER_QUEUE (60) per queue
    python refresh_urls.py --apply <RUN_ID>     # ingest a finished run, no new scrape
    PER_QUEUE=120 python refresh_urls.py        # deeper pass

A queue with >= TARGET_IMAGES (30) confirmed images already is skipped.
Needs APIFY_API_TOKEN in eval/calibration/.env. Run cost capped at $5.
NOTE: rebuilding the dataset (`calibrate.py build`) restores full queues and
stale urls -- re-run this with no args (or --apply) afterwards to re-patch.
"""

import json
import os
import re
import sys
import time

from calibrate import DATA_DIR, DATASET_PATH, load_env, require, get_requests

ACTOR = "apify~instagram-scraper"
TRIED_PATH = os.path.join(DATA_DIR, "refresh_tried.json")
SHORTCODE_RE = re.compile(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)")


def shortcode(url):
    m = SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def load_tried():
    if os.path.exists(TRIED_PATH):
        with open(TRIED_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def record_items(items, by_shortcode, tried):
    """Fold scraped items into the tried map (post id -> {type, url})."""
    unmatched = 0
    for it in items:
        sc = it.get("shortCode") or shortcode(it.get("url"))
        e = by_shortcode.get(sc)
        if e is None:
            unmatched += 1
            continue
        kind = "video" if (it.get("type") or "").lower() == "video" else "image"
        url = it.get("displayUrl") or (it.get("images") or [None])[0]
        tried[e["id"]] = {"type": kind, "url": url if kind == "image" else None}
    return unmatched


def patch_dataset(ds, tried):
    """Apply fresh urls; prune the download-facing queues to confirmed-image
    refreshed posts, keeping the originals in candidates_full for later
    passes."""
    fresh = 0
    for e in ds["posts"]:
        t = tried.get(e["id"])
        if t and t.get("url"):
            e["media_url"] = t["url"]
            e.pop("download_error", None)
            fresh += 1
    full = ds.get("candidates_full") or ds["candidates"]
    ds["candidates_full"] = full
    ok = {pid for pid, t in tried.items() if t.get("url")}
    ds["candidates"] = {k: [pid for pid in v if pid in ok] for k, v in full.items()}
    ds["candidates"] = {k: v for k, v in ds["candidates"].items() if v}
    return fresh


def fetch_dataset_items(requests, token, dataset_id):
    items, offset = [], 0
    while True:
        r = requests.get(f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                         params={"token": token, "offset": offset, "limit": 1000},
                         timeout=60)
        r.raise_for_status()
        chunk = r.json()
        items.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000
    return items


def main():
    load_env()
    requests = get_requests()
    token = require("APIFY_API_TOKEN")
    tried = load_tried()

    with open(DATASET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    by_shortcode = {shortcode(e.get("post_url")): e for e in ds["posts"]
                    if shortcode(e.get("post_url"))}

    if len(sys.argv) > 2 and sys.argv[1] == "--apply":
        run_id = sys.argv[2]
        rd = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}",
                          params={"token": token}, timeout=30)
        rd.raise_for_status()
        items = fetch_dataset_items(requests, token,
                                    rd.json()["data"]["defaultDatasetId"])
        unmatched = record_items(items, by_shortcode, tried)
        print(f"applied run {run_id}: {len(items)} items, {unmatched} unmatched")
    else:
        per_queue = int(os.environ.get("PER_QUEUE", "60"))
        target = int(os.environ.get("TARGET_IMAGES", "30"))
        targets, picked = {}, {}
        full = ds.get("candidates_full") or ds["candidates"]
        for qname, queue in sorted(full.items()):
            if not qname.startswith("instagram|"):
                continue
            have = sum(1 for pid in queue if tried.get(pid, {}).get("url"))
            if have >= target:
                picked[qname] = f"skip (has {have} images)"
                continue
            n = 0
            for pid in queue:
                if pid in tried:
                    continue
                sc = shortcode(posts[pid].get("post_url"))
                if sc and sc not in targets:
                    targets[sc] = posts[pid]
                    n += 1
                if n >= per_queue:
                    break
            picked[qname] = n
        print("scraping " + " ".join(f"{k}={n}" for k, n in picked.items()))
        if not targets:
            print("nothing to scrape; just re-patching dataset")
        else:
            run = requests.post(
                f"https://api.apify.com/v2/acts/{ACTOR}/runs",
                params={"token": token, "maxTotalChargeUsd": 5},
                json={"directUrls": [e["post_url"] for e in targets.values()],
                      "resultsType": "posts", "resultsLimit": len(targets)},
                timeout=60)
            run.raise_for_status()
            rd = run.json()["data"]
            run_id, dataset_id = rd["id"], rd["defaultDatasetId"]
            print(f"run {run_id} started "
                  f"(https://console.apify.com/actors/runs/{run_id})")
            deadline = time.time() + 30 * 60
            while True:
                st = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}",
                                  params={"token": token}, timeout=30).json()["data"]
                if st["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                    break
                if time.time() > deadline:
                    sys.exit(f"run {run_id} still {st['status']} after 30min -- "
                             f"ingest later with: refresh_urls.py --apply {run_id}")
                time.sleep(15)
            if st["status"] != "SUCCEEDED":
                sys.exit(f"run {run_id} ended {st['status']} -- dataset untouched")
            items = fetch_dataset_items(requests, token, dataset_id)
            unmatched = record_items(items, by_shortcode, tried)
            print(f"run returned {len(items)} items ({unmatched} unmatched)")

    with open(TRIED_PATH, "w", encoding="utf-8") as f:
        json.dump(tried, f, ensure_ascii=False)
    fresh = patch_dataset(ds, tried)
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False)
    n_img = sum(1 for t in tried.values() if t.get("url"))
    n_vid = sum(1 for t in tried.values() if not t.get("url"))
    print(f"tried {len(tried)} posts total: {n_img} images, {n_vid} videos/none")
    print(f"dataset patched ({fresh} fresh urls); queues now: "
          + " ".join(f"{k}={len(v)}" for k, v in sorted(ds["candidates"].items())))


if __name__ == "__main__":
    main()
