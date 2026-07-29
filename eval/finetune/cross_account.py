"""Cross-account validation: does the fine-tuned ranker generalize beyond
@samsunggulf?

Picks the Instagram account with the most posts in the SamsungSentiment
export (excluding the brand), builds within-account engagement percentiles
(same cohorting as the calibration study), scrapes fresh URLs for its
top/bottom-quartile images via Apify directUrls, downloads them, scores them
through the deployed ranker endpoint, and reports AUC.

    python eval/finetune/cross_account.py            # auto-pick account
    ACCOUNT=somebrand python eval/finetune/cross_account.py
"""

import json
import os
import subprocess
import sys
import time

FT_DIR = os.path.dirname(os.path.abspath(__file__))
CAL_DIR = os.path.normpath(os.path.join(FT_DIR, "..", "calibration"))
sys.path.insert(0, CAL_DIR)

from calibrate import (POSTS_PATH, load_env, require, get_requests, media_kind,
                       quarter, _percentiles, _dt, auc, CONTEST_RE, EVENT_RE,
                       MIN_COHORT, MIN_AGE_DAYS, UA)
from refresh_urls import ACTOR, shortcode

DATA_DIR = os.path.join(FT_DIR, "data", "cross_account")
RANK_URL = "https://mohamedymay7--rank.modal.run"
PER_STRATUM = int(os.environ.get("PER_STRATUM", "40"))  # scrape budget per stratum


def rank_via_curl(image_path):
    """python-requests hits a local TLS quirk on the ranker host; curl works."""
    import base64
    body = json.dumps({"image_b64": base64.b64encode(open(image_path, "rb").read()).decode()})
    body_path = os.path.join(DATA_DIR, "_body.json")
    with open(body_path, "w") as f:
        f.write(body)
    for attempt in (1, 2, 3):
        r = subprocess.run(["curl", "-sS", "-m", "600", "-X", "POST",
                            "-H", "Content-Type: application/json",
                            "-d", "@" + body_path, RANK_URL],
                           capture_output=True, text=True)
        try:
            return json.loads(r.stdout)["raw"]
        except Exception:
            if attempt == 3:
                raise RuntimeError(f"rank call failed: {r.stdout[:200] or r.stderr[:200]}")
            time.sleep(20)


def main():
    load_env()
    requests = get_requests()
    token = require("APIFY_API_TOKEN")
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(POSTS_PATH, encoding="utf-8") as f:
        posts = json.load(f)
    ig = [p for p in posts if p["platform"] == "instagram"]

    account = os.environ.get("ACCOUNT")
    if not account:
        counts = {}
        for p in ig:
            o = (p.get("owner_ig") or "").strip().lower()
            if o and o != "samsunggulf":
                counts[o] = counts.get(o, 0) + 1
        account = max(counts, key=counts.get)
        print(f"largest non-brand IG account: {account} ({counts[account]} posts)")

    from datetime import timedelta
    newest = max(filter(None, (_dt(p.get("published_at")) for p in posts)))
    cutoff = newest - timedelta(days=MIN_AGE_DAYS)
    rows = []
    for p in ig:
        if (p.get("owner_ig") or "").strip().lower() != account:
            continue
        kind = media_kind(p)
        eng = (p.get("likes_count") or 0) + (p.get("comments_count") or 0) + (p.get("shares_count") or 0)
        cap = p.get("caption") or ""
        pub = _dt(p.get("published_at"))
        if kind != "image" or eng == 0 or (pub and pub > cutoff):
            continue
        if CONTEST_RE.search(cap) or EVENT_RE.search(cap):
            continue
        rows.append({"id": p["id"], "post_url": p.get("post_url"), "metric": float(eng),
                     "published_at": p.get("published_at"), "engagement": eng})

    # percentile within quarter when the quarter is big enough; thin quarters
    # pool into one merged cohort
    cohorts = {}
    for e in rows:
        cohorts.setdefault(quarter(e["published_at"]), []).append(e)
    big = [g for g in cohorts.values() if len(g) >= MIN_COHORT]
    small = [e for g in cohorts.values() if len(g) < MIN_COHORT for e in g]
    for g in big + ([small] if small else []):
        _percentiles(g)
    strata = {"top": [e for e in rows if e["percentile"] >= 75],
              "bottom": [e for e in rows if e["percentile"] <= 25]}
    print(f"{account}: {len(rows)} mature image posts; "
          f"top={len(strata['top'])} bottom={len(strata['bottom'])}")

    targets = {}
    for st, group in strata.items():
        group.sort(key=lambda e: abs(e["percentile"] - 50), reverse=True)
        for e in group[:PER_STRATUM]:
            sc = shortcode(e["post_url"])
            if sc:
                e["stratum"] = st
                targets[sc] = e
    print(f"scraping {len(targets)} post urls via Apify...")
    run = requests.post(
        f"https://api.apify.com/v2/acts/{ACTOR}/runs",
        params={"token": token, "maxTotalChargeUsd": 5},
        json={"directUrls": [e["post_url"] for e in targets.values()],
              "resultsType": "posts", "resultsLimit": len(targets)},
        timeout=60)
    run.raise_for_status()
    rd = run.json()["data"]
    while True:
        st = requests.get(f"https://api.apify.com/v2/actor-runs/{rd['id']}",
                          params={"token": token}, timeout=30).json()["data"]
        if st["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        time.sleep(15)
    if st["status"] != "SUCCEEDED":
        sys.exit(f"apify run {rd['id']} ended {st['status']}")
    items = requests.get(
        f"https://api.apify.com/v2/datasets/{rd['defaultDatasetId']}/items",
        params={"token": token, "limit": 1000}, timeout=60).json()

    scored, failures = [], 0
    for it in items:
        e = targets.get(it.get("shortCode") or shortcode(it.get("url")))
        if e is None or (it.get("type") or "").lower() == "video":
            continue
        url = it.get("displayUrl") or (it.get("images") or [None])[0]
        if not url:
            continue
        try:
            img_path = os.path.join(DATA_DIR, e["id"] + ".jpg")
            if not os.path.exists(img_path):
                r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
                if r.status_code != 200 or "image" not in r.headers.get("content-type", ""):
                    continue
                with open(img_path, "wb") as f:
                    f.write(r.content)
            score = rank_via_curl(img_path)
        except Exception as exc:
            failures += 1
            print(f"  [{e['stratum']:<6}] SKIP {type(exc).__name__}: {str(exc)[:90]}",
                  flush=True)
            continue
        scored.append({**e, "rank_raw": score})
        print(f"  [{e['stratum']:<6}] pct={e['percentile']:<5} rank_raw={score:.2f}",
              flush=True)
    if failures:
        print(f"({failures} items skipped on download/rank errors)")

    top = [e["rank_raw"] for e in scored if e["stratum"] == "top"]
    bot = [e["rank_raw"] for e in scored if e["stratum"] == "bottom"]
    with open(os.path.join(DATA_DIR, f"{account}_results.json"), "w", encoding="utf-8") as f:
        json.dump(scored, f, ensure_ascii=False)
    print(f"\nCROSS-ACCOUNT ({account}): n={len(scored)} "
          f"({len(top)} top / {len(bot)} bottom) AUC {auc(top, bot):.3f}")


if __name__ == "__main__":
    main()
