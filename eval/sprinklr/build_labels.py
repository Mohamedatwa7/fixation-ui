"""Sprinklr export -> cohort-normalized engagement labels.

No paid/organic flag exists in this export, so labels are designed to be
robust to paid amplification:
- metric = engagement RATE (engagements per exposed viewer), not counts —
  bought delivery inflates numerator and denominator together;
- percentile ranks are computed WITHIN platform x campaign x quarter
  cohorts, so campaign-level boosting patterns can't leak across cohorts;
- small cohorts merge quarters (platform x campaign), then fall back to
  platform-only, mirroring eval/calibration/calibrate.py.

    python eval/sprinklr/build_labels.py

Outputs data/labels.json: one row per post with exposure, engagement rate,
cohort id and percentile — the media-acquisition and pair-building steps
consume this.
"""

import csv
import json
import os
import re
from collections import defaultdict

SPR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SPR_DIR, "data")
CSV_PATH = r"C:\Users\Hi\Downloads\Sprinklr Data(Sheet1).csv"
OUT = os.path.join(DATA_DIR, "labels.json")

MIN_EXPOSURE = 300      # below this, engagement rate is noise
MIN_COHORT = 8          # smaller cohorts merge up


def quarter(ts):
    m = re.match(r"(\d+)/\d+/(\d+)", ts or "")
    if not m:
        return "unknown"
    month, year = int(m.group(1)), m.group(2)
    return f"{year}Q{(month - 1) // 3 + 1}"


def video_kind(url):
    u = (url or "").lower()
    if "/reel/" in u or "/shorts/" in u or "watch?v=" in u or "youtu" in u:
        return "video"
    if "/p/" in u:
        return "image_or_carousel"
    return "unknown"


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CSV_PATH, encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.DictReader(f))
    posts = []
    for r in rows:
        reach = int(float(r["Post Reach (SUM)"] or 0))
        views = int(float(r["YouTube Video Views (SUM)"] or 0))
        eng = int(float(r["Total Engagements (SUM)"] or 0))
        exposure = max(reach, views)
        if exposure < MIN_EXPOSURE:
            continue
        posts.append({
            "platform": r["Account Type"],
            "url": r["Permalink"],
            "campaign": r["Campaign Name"] or "(none)",
            "quarter": quarter(r["PublishedTime"]),
            "caption": (r["Outbound Post"] or "")[:200],
            "exposure": exposure,
            "engagements": eng,
            "er": eng / exposure,
            "kind": video_kind(r["Permalink"]),
        })
    print(f"{len(rows)} rows -> {len(posts)} with exposure >= {MIN_EXPOSURE}")

    # cohort assembly with merge-up fallback
    def coh3(p): return (p["platform"], p["campaign"], p["quarter"])
    def coh2(p): return (p["platform"], p["campaign"])
    def coh1(p): return (p["platform"],)
    counts3 = defaultdict(int)
    counts2 = defaultdict(int)
    for p in posts:
        counts3[coh3(p)] += 1
        counts2[coh2(p)] += 1
    groups = defaultdict(list)
    for p in posts:
        if counts3[coh3(p)] >= MIN_COHORT:
            key = coh3(p)
        elif counts2[coh2(p)] >= MIN_COHORT:
            key = coh2(p)
        else:
            key = coh1(p)
        p["cohort"] = " / ".join(key)
        groups[p["cohort"]].append(p)
    for cohort, grp in groups.items():
        grp.sort(key=lambda p: p["er"])
        n = len(grp)
        for i, p in enumerate(grp):
            p["percentile"] = round(100.0 * (i + 0.5) / n, 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(posts, f)

    from collections import Counter
    plat = Counter(p["platform"] for p in posts)
    kinds = Counter((p["platform"], p["kind"]) for p in posts)
    print(f"cohorts: {len(groups)} (median size "
          f"{sorted(len(g) for g in groups.values())[len(groups)//2]})")
    print("labeled posts by platform:", dict(plat))
    print("by platform x kind:", dict(kinds))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
