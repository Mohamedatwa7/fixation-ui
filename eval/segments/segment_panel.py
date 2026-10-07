"""Segment panels: scrape audience-known Gulf accounts, build per-segment
engagement cohorts.

Builds the dataset that turns "would this work for 30-40yo women?" from
persona simulation into measured evidence: for each segment, posts from
accounts whose audience skews that way, with within-account engagement
percentiles (same cohort-normalization idea as eval/calibration).

    python eval/segments/segment_panel.py scrape    # Apify runs (budgeted)
    python eval/segments/segment_panel.py build     # percentiles + report

BUDGET GUARD: hard-capped via MAX_TOTAL_RESULTS and per-profile
RESULTS_PER_PROFILE. At Apify's pay-per-result pricing (~$2.3-2.6/1000
items for the Instagram scrapers) the full default scrape is ~2.1k items
=~ $6; the cap stops new runs long before $80 of usage.

Instagram accounts only (the profile scraper); YouTube/TikTok-only entries
are skipped and listed in the report. Token: APIFY_API_TOKEN from
eval/calibration/.env.
"""

import json
import os
import sys
import time

SEG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SEG_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
ACCOUNTS_PATH = os.path.join(SEG_DIR, "segment_accounts.json")
PANELS_PATH = os.path.join(DATA_DIR, "segment_panels.json")
REPORT_PATH = os.path.join(DATA_DIR, "REPORT.md")

ACTOR = "apify~instagram-profile-scraper"
RESULTS_PER_PROFILE = 50
MAX_TOTAL_RESULTS = 15000      # ~ $35-40 absolute worst case; default ~2.1k
EST_COST_PER_1K = 2.60         # USD, conservative
RUN_TIMEOUT_S = 1800


def _token():
    env = os.path.join(os.path.dirname(SEG_DIR), "calibration", ".env")
    for line in open(env, encoding="utf-8"):
        if line.startswith("APIFY_API_TOKEN="):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("APIFY_API_TOKEN not found in eval/calibration/.env")


def _ig_handles():
    with open(ACCOUNTS_PATH, encoding="utf-8") as f:
        spec = json.load(f)
    plan, skipped = {}, []
    for seg, body in spec["segments"].items():
        handles = []
        for acc in body["accounts"]:
            if "instagram" in acc["platform"]:
                handles.append(acc["handle"])
            else:
                skipped.append((seg, acc["handle"], acc["platform"]))
        plan[seg] = handles
    return plan, skipped


def cmd_scrape():
    import requests
    token = _token()
    os.makedirs(RAW_DIR, exist_ok=True)
    plan, skipped = _ig_handles()
    total_requested = 0
    for seg, handles in plan.items():
        out_path = os.path.join(RAW_DIR, f"{seg}.json")
        if os.path.exists(out_path):
            print(f"[{seg}] already scraped, skipping")
            continue
        budget_items = len(handles) * RESULTS_PER_PROFILE
        if total_requested + budget_items > MAX_TOTAL_RESULTS:
            print(f"[{seg}] BUDGET CAP reached ({total_requested} requested) — stopping")
            break
        total_requested += budget_items
        print(f"[{seg}] launching run for {len(handles)} profiles "
              f"(cum. est ${total_requested / 1000 * EST_COST_PER_1K:.2f})")
        r = requests.post(
            f"https://api.apify.com/v2/acts/{ACTOR}/runs",
            params={"token": token},
            json={"usernames": handles, "resultsLimit": RESULTS_PER_PROFILE},
            timeout=60)
        r.raise_for_status()
        run = r.json()["data"]
        run_id = run["id"]
        t0 = time.time()
        while time.time() - t0 < RUN_TIMEOUT_S:
            time.sleep(20)
            s = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}",
                             params={"token": token}, timeout=60).json()["data"]
            if s["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        print(f"[{seg}] run {s['status']} in {time.time()-t0:.0f}s")
        if s["status"] != "SUCCEEDED":
            print(f"[{seg}] skipping dataset download (status={s['status']})")
            continue
        items = requests.get(
            f"https://api.apify.com/v2/datasets/{s['defaultDatasetId']}/items",
            params={"token": token, "format": "json"}, timeout=300).json()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(items, f)
        print(f"[{seg}] saved {len(items)} profile records -> {out_path}", flush=True)
    if skipped:
        print(f"{len(skipped)} non-instagram accounts skipped")


def cmd_build():
    plan, skipped = _ig_handles()
    panels = {}
    lines = ["# Segment panels — scrape summary", ""]
    for seg in plan:
        path = os.path.join(RAW_DIR, f"{seg}.json")
        if not os.path.exists(path):
            lines.append(f"- {seg}: NOT SCRAPED")
            continue
        with open(path, encoding="utf-8") as f:
            profiles = json.load(f)
        accounts = {}
        for prof in profiles:
            handle = prof.get("username") or prof.get("id")
            posts = prof.get("latestPosts") or []
            rows = []
            for p in posts:
                likes = p.get("likesCount")
                comments = p.get("commentsCount") or 0
                if not isinstance(likes, (int, float)) or likes < 0:
                    continue
                rows.append({
                    "post_id": p.get("id") or p.get("shortCode"),
                    "url": p.get("url"),
                    "type": p.get("type"),
                    "caption": (p.get("caption") or "")[:300],
                    "display_url": p.get("displayUrl"),
                    "timestamp": p.get("timestamp"),
                    "engagement": likes + comments,
                })
            # within-account percentile — controls for audience size/platform
            rows.sort(key=lambda r: r["engagement"])
            n = len(rows)
            for rank, row in enumerate(rows):
                row["pctl_in_account"] = round(100.0 * (rank + 0.5) / n, 1) if n else None
            if rows:
                accounts[handle] = {
                    "followers": prof.get("followersCount"),
                    "n_posts": n,
                    "posts": rows,
                }
        panels[seg] = accounts
        total_posts = sum(a["n_posts"] for a in accounts.values())
        missing = [h for h in plan[seg] if h not in accounts]
        lines.append(f"- **{seg}**: {len(accounts)}/{len(plan[seg])} accounts, "
                     f"{total_posts} posts" +
                     (f" — missing/unverified: {', '.join(missing)}" if missing else ""))
    if skipped:
        lines += ["", "Skipped (non-Instagram): " +
                  ", ".join(f"{h} ({p})" for _, h, p in skipped)]
    with open(PANELS_PATH, "w", encoding="utf-8") as f:
        json.dump(panels, f)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    {"scrape": cmd_scrape, "build": cmd_build}[
        sys.argv[1] if len(sys.argv) > 1 else "scrape"]()
