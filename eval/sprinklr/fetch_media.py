"""Sprinklr chain A: fetch creatives + account identity for labeled posts.

- YOUTUBE: yt-dlp metadata (--dump-json, no download) gives channel (the
  ACCOUNT) + thumbnail URL; thumbnail downloaded as the creative. Free.
- INSTAGRAM / FBPAGE: Apify by-URL scrapers return media URL + owner
  username / page name (the ACCOUNT) + full caption. Budget-guarded.

Account identity is captured because scores must be interpretable per
posting account; full captions are stored for future caption-effect work.

    python eval/sprinklr/fetch_media.py yt      # free, ~45min
    python eval/sprinklr/fetch_media.py ig      # Apify ~$3
    python eval/sprinklr/fetch_media.py fb      # Apify ~$8-15
    python eval/sprinklr/fetch_media.py images  # download media files

Outputs: data/media_meta.json {url -> {account, caption_full, media_url,
thumb}}, media files in data/media/<sha>.jpg.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time

SPR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SPR_DIR, "data")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
LABELS = os.path.join(DATA_DIR, "labels.json")
META = os.path.join(DATA_DIR, "media_meta.json")

MAX_APIFY_RESULTS = 8000           # hard budget guard (~$40 worst case)
EST_COST_PER_1K = 5.0              # conservative blended estimate
YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp.exe")


def load_meta():
    if os.path.exists(META):
        with open(META, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(meta):
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def posts_for(platform):
    with open(LABELS, encoding="utf-8") as f:
        return [p for p in json.load(f) if p["platform"] == platform]


def _apify_token():
    env = os.path.join(os.path.dirname(SPR_DIR), "calibration", ".env")
    for line in open(env, encoding="utf-8"):
        if line.startswith("APIFY_API_TOKEN="):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("APIFY_API_TOKEN missing")


def cmd_yt():
    os.makedirs(MEDIA_DIR, exist_ok=True)
    meta = load_meta()
    posts = [p for p in posts_for("YOUTUBE") if p["url"] not in meta]
    print(f"{len(posts)} YT posts to resolve")
    ytdlp = YTDLP if os.path.exists(YTDLP) else "yt-dlp"
    for i, p in enumerate(posts, 1):
        try:
            r = subprocess.run(
                [ytdlp, "--dump-json", "--skip-download", "--no-warnings",
                 p["url"]],
                capture_output=True, text=True, timeout=60, encoding="utf-8",
                errors="replace")
            if r.returncode != 0:
                meta[p["url"]] = {"error": (r.stderr or "")[-200:]}
            else:
                j = json.loads(r.stdout)
                meta[p["url"]] = {
                    "account": j.get("channel") or j.get("uploader"),
                    "caption_full": (j.get("description") or "")[:2000],
                    "title": j.get("title"),
                    "media_url": j.get("thumbnail"),
                    "duration": j.get("duration"),
                }
        except Exception as e:
            meta[p["url"]] = {"error": repr(e)[:200]}
        if i % 50 == 0:
            save_meta(meta)
            print(f"  {i}/{len(posts)}", flush=True)
    save_meta(meta)
    ok = sum(1 for p in posts_for('YOUTUBE')
             if meta.get(p['url'], {}).get('media_url'))
    print(f"YT resolved: {ok}/{len(posts_for('YOUTUBE'))}")


def _apify_run(actor, payload, est_items):
    import requests
    token = _apify_token()
    state_p = os.path.join(DATA_DIR, "apify_spend.json")
    spent = json.load(open(state_p))["items"] if os.path.exists(state_p) else 0
    if spent + est_items > MAX_APIFY_RESULTS:
        raise RuntimeError(f"budget guard: {spent}+{est_items} > {MAX_APIFY_RESULTS}")
    r = requests.post(f"https://api.apify.com/v2/acts/{actor}/runs",
                      params={"token": token}, json=payload, timeout=60)
    r.raise_for_status()
    run_id = r.json()["data"]["id"]
    t0 = time.time()
    while time.time() - t0 < 3600:
        time.sleep(30)
        s = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}",
                         params={"token": token}, timeout=60).json()["data"]
        if s["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    print(f"  run {s['status']} after {time.time()-t0:.0f}s")
    if s["status"] != "SUCCEEDED":
        return []
    items = requests.get(
        f"https://api.apify.com/v2/datasets/{s['defaultDatasetId']}/items",
        params={"token": token, "format": "json"}, timeout=600).json()
    with open(state_p, "w", encoding="utf-8") as f:
        json.dump({"items": spent + len(items),
                   "est_cost_usd": round((spent + len(items)) / 1000 * EST_COST_PER_1K, 2)}, f)
    return items


def cmd_ig():
    meta = load_meta()
    posts = [p for p in posts_for("INSTAGRAM") if p["url"] not in meta]
    print(f"{len(posts)} IG posts to resolve")
    for i in range(0, len(posts), 300):
        chunk = posts[i:i + 300]
        items = _apify_run("apify~instagram-scraper",
                           {"directUrls": [p["url"] for p in chunk],
                            "resultsType": "posts", "resultsLimit": 1},
                           len(chunk))
        by_short = {}
        for it in items:
            key = it.get("url") or ""
            by_short[re.sub(r"/$", "", key)] = it
        for p in chunk:
            it = by_short.get(re.sub(r"/$", "", p["url"]))
            if not it:
                meta[p["url"]] = {"error": "not returned"}
                continue
            meta[p["url"]] = {
                "account": it.get("ownerUsername"),
                "caption_full": (it.get("caption") or "")[:2000],
                "media_url": it.get("displayUrl"),
                "video_url": it.get("videoUrl"),
            }
        save_meta(meta)
        print(f"  {min(i+300, len(posts))}/{len(posts)}", flush=True)


def cmd_fb():
    meta = load_meta()
    posts = [p for p in posts_for("FBPAGE") if p["url"] not in meta]
    print(f"{len(posts)} FB posts to resolve")
    for i in range(0, len(posts), 400):
        chunk = posts[i:i + 400]
        items = _apify_run("apify~facebook-posts-scraper",
                           {"startUrls": [{"url": p["url"]} for p in chunk],
                            "resultsLimit": 1},
                           len(chunk))
        by_url = {}
        for it in items:
            for k in ("url", "postUrl", "topLevelUrl", "inputUrl"):
                if it.get(k):
                    by_url[re.sub(r"/$", "", str(it[k]))] = it
        for p in chunk:
            it = by_url.get(re.sub(r"/$", "", p["url"]))
            if not it:
                meta[p["url"]] = {"error": "not returned"}
                continue
            media = it.get("media") or []
            murl = None
            for m in media:
                murl = (m.get("photo_image") or {}).get("uri") or \
                       m.get("thumbnail") or murl
            meta[p["url"]] = {
                "account": it.get("pageName") or (it.get("user") or {}).get("name"),
                "caption_full": (it.get("text") or "")[:2000],
                "media_url": murl,
            }
        save_meta(meta)
        print(f"  {min(i+400, len(posts))}/{len(posts)}", flush=True)


def cmd_images():
    import requests
    os.makedirs(MEDIA_DIR, exist_ok=True)
    meta = load_meta()
    todo = [(u, m) for u, m in meta.items()
            if m.get("media_url") and not m.get("file")]
    print(f"{len(todo)} media files to download")
    for i, (url, m) in enumerate(todo, 1):
        name = hashlib.sha1(url.encode()).hexdigest()[:20] + ".jpg"
        path = os.path.join(MEDIA_DIR, name)
        try:
            if not os.path.exists(path):
                r = requests.get(m["media_url"], timeout=60,
                                 headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                if len(r.content) < 2000:
                    raise ValueError("too small")
                with open(path, "wb") as f:
                    f.write(r.content)
            m["file"] = name
        except Exception as e:
            m["file_error"] = repr(e)[:150]
        if i % 100 == 0:
            save_meta(meta)
            print(f"  {i}/{len(todo)}", flush=True)
    save_meta(meta)
    ok = sum(1 for m in meta.values() if m.get("file"))
    print(f"media files on disk: {ok}")


if __name__ == "__main__":
    {"yt": cmd_yt, "ig": cmd_ig, "fb": cmd_fb, "images": cmd_images}[sys.argv[1]]()
