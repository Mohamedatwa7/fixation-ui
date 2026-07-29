"""F1X8 calibration study (step 1): does the deployed Engagement Potential
score track realized organic engagement on @samsunggulf creatives?

Data source: the SamsungSentiment Supabase (`social_posts`, scraped nightly by
Apify). Labels are cohort-normalized engagement percentiles — rank within
platform x media-kind x quarter, so follower growth and platform baselines
don't leak into the label. Only clearly-attributable image creatives are
scored in this pass (TikTok rows are videos; video scoring is a follow-up).

    python eval/calibration/calibrate.py export     # Supabase -> data/posts.json
    python eval/calibration/calibrate.py build      # filter + percentiles -> data/dataset.json
    python eval/calibration/calibrate.py download   # media for the stratified sample -> data/media/
    python eval/calibration/calibrate.py run        # score sample via the deployed F1X8 API
    python eval/calibration/calibrate.py report     # data/REPORT.md  (Spearman + top-vs-bottom AUC)
    python eval/calibration/calibrate.py all

Config via env or eval/calibration/.env:
    SUPABASE_URL    https://<project>.supabase.co
    SUPABASE_KEY    anon key is enough (RLS allows public SELECT on social_posts)
    F1X8_API_URL    Modal base URL (https://...modal.run) or the deployed
                    Vercel site (https://...vercel.app — proxied via /api/analyze)
    SAMPLE_CAP      max creatives to score (default 60, split top/bottom quartile)
"""

import json
import math
import os
import random
import re
import sys
import time

CAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CAL_DIR, "data")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
POSTS_PATH = os.path.join(DATA_DIR, "posts.json")
DATASET_PATH = os.path.join(DATA_DIR, "dataset.json")
REPORT_PATH = os.path.join(DATA_DIR, "REPORT.md")

MIN_COHORT = 8          # smaller cohorts get merged across quarters
MIN_VIEWS = 100         # below this, per-view rates are noise
MIN_AGE_DAYS = 14       # engagement accumulates for days after posting; younger
                        # posts carry an immature (biased-low) label
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Engagement on these posts is driven by the mechanic or the news moment, not
# the creative, so they poison the label. Contest posts are dropped; event-hype
# posts (Unpacked etc.) are kept out of the pool but counted in the report.
CONTEST_RE = re.compile(
    r"giveaway|give\s?away|contest|competition|\bwinners?\b|\bprizes?\b|"
    r"\bwin\b|tag a friend|comment\s+#?\w+ (with|if|and)|سحب|مسابقة|"
    r"اربح|جائزة", re.I)
EVENT_RE = re.compile(r"unpacked|أنباكد", re.I)

IMAGE_URL_RE = re.compile(r"\.(jpe?g|png|webp)([?#]|$)|format=(jpe?g|png|webp)", re.I)
VIDEO_URL_RE = re.compile(r"\.(mp4|mov|m3u8)([?#]|$)", re.I)


def load_env():
    env_path = os.path.join(CAL_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


def require(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"{name} is not set -- add it to eval/calibration/.env (see module docstring)")
    return v


def get_requests():
    try:
        import requests
        return requests
    except ImportError:
        sys.exit("the 'requests' package is required: pip install requests")


# ---------------------------------------------------------------- export

def cmd_export():
    requests = get_requests()
    base, key = require("SUPABASE_URL").rstrip("/"), require("SUPABASE_KEY")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    # owner columns mirror BRAND_POST_COLUMNS in SamsungSentiment's
    # apify-sync.ts: social_posts also holds retailer/operator and influencer
    # accounts from other scrapes, which must not enter the brand cohorts.
    fields = ("id,platform,external_id,post_url,caption,media_type,media_url,"
              "likes_count,comments_count,shares_count,views_count,published_at,"
              "owner_ig:raw_data->>ownerUsername,owner_tt:raw_data->authorMeta->>name,"
              "owner_fb:raw_data->>pageName,owner_tw:raw_data->author->>userName")
    posts, offset, page = [], 0, 1000
    while True:
        r = requests.get(
            f"{base}/rest/v1/social_posts",
            params={"select": fields, "order": "id.asc",
                    "offset": offset, "limit": page},
            headers=headers, timeout=60)
        r.raise_for_status()
        chunk = r.json()
        posts.extend(chunk)
        print(f"  fetched {len(posts)} posts...")
        if len(chunk) < page:
            break
        offset += page
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False)
    by = {}
    for p in posts:
        k = (p["platform"], (p.get("media_type") or "?").lower())
        by[k] = by.get(k, 0) + 1
    print(f"exported {len(posts)} posts -> {POSTS_PATH}")
    for (plat, mt), n in sorted(by.items()):
        print(f"  {plat:<10} {mt:<10} {n}")


# ---------------------------------------------------------------- build

def media_kind(post):
    """'image' | 'video' | None (no scoreable media)."""
    url = post.get("media_url") or ""
    mt = (post.get("media_type") or "").lower()
    if not url:
        return None
    if post["platform"] == "tiktok":
        return "video"  # media_url is only the cover thumbnail
    if mt in ("image", "photo", "sidecar"):
        return "image"
    # media_type video/reel wins over the URL heuristic: IG reels carry a .jpg
    # thumbnail as media_url and must NOT be classified as images (they used
    # to be, contaminating the image cohorts' percentiles).
    if mt in ("video", "reel"):
        return "video"
    # twitter's media_type says 'video' for any media array — trust the URL
    if IMAGE_URL_RE.search(url):
        return "image"
    if VIDEO_URL_RE.search(url):
        return "video"
    return None


def quarter(iso):
    return f"{iso[:4]}Q{(int(iso[5:7]) - 1) // 3 + 1}" if iso else "?"


def _dt(iso):
    from datetime import datetime
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None


BRAND_OWNERS = {"samsunggulf", "samsung gulf", "samsunggulf.official"}


def owner_of(post):
    return (post.get("owner_ig") or post.get("owner_tt") or post.get("owner_fb")
            or post.get("owner_tw") or "").strip().lower()


def _percentiles(group):
    """Average-rank percentile (0-100) of each post's metric within its cohort."""
    ranked = sorted(range(len(group)), key=lambda i: group[i]["metric"])
    pct = [0.0] * len(group)
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and group[ranked[j + 1]]["metric"] == group[ranked[i]]["metric"]:
            j += 1
        avg_rank = (i + j) / 2
        for k in range(i, j + 1):
            pct[ranked[k]] = 100 * avg_rank / max(len(group) - 1, 1)
        i = j + 1
    for post, p in zip(group, pct):
        post["percentile"] = round(p, 1)


def cmd_build():
    with open(POSTS_PATH, encoding="utf-8") as f:
        posts = json.load(f)

    # age is measured against the newest post in the snapshot, not wall clock,
    # so a rebuild from the same export is deterministic
    from datetime import timedelta
    newest = max(filter(None, (_dt(p.get("published_at")) for p in posts)), default=None)
    cutoff = newest - timedelta(days=MIN_AGE_DAYS) if newest else None

    eligible, dropped = [], {"other_account": 0, "owner_unknown": 0, "no_media": 0,
                             "no_engagement": 0, "too_recent": 0,
                             "contest": 0, "event": 0}
    for p in posts:
        kind = media_kind(p)
        eng = (p.get("likes_count") or 0) + (p.get("comments_count") or 0) + (p.get("shares_count") or 0)
        views = p.get("views_count") or 0
        caption = p.get("caption") or ""
        published = _dt(p.get("published_at"))
        owner = owner_of(p)
        if owner and owner not in BRAND_OWNERS:
            dropped["other_account"] += 1
        elif not owner:
            dropped["owner_unknown"] += 1
        elif kind is None:
            dropped["no_media"] += 1
        elif eng + views == 0:  # all-zero rows are scrape gaps, not real duds
            dropped["no_engagement"] += 1
        elif cutoff and published and published > cutoff:
            dropped["too_recent"] += 1
        elif CONTEST_RE.search(caption):
            dropped["contest"] += 1
        elif EVENT_RE.search(caption):
            dropped["event"] += 1
        else:
            if kind == "video" and views >= MIN_VIEWS:
                basis, metric = "per_view", eng / views
            else:
                basis, metric = "raw", float(eng)
            eligible.append({
                "id": p["id"], "platform": p["platform"], "kind": kind,
                "basis": basis, "metric": metric, "media_url": p["media_url"],
                "post_url": p.get("post_url"), "published_at": p.get("published_at"),
                "caption": caption[:200], "engagement": eng, "views": views,
            })

    # cohort = platform x kind x basis x quarter; merge quarters when thin
    cohorts = {}
    for e in eligible:
        key = (e["platform"], e["kind"], e["basis"], quarter(e["published_at"]))
        cohorts.setdefault(key, []).append(e)
    merged = {}
    for key, group in cohorts.items():
        target = key if len(group) >= MIN_COHORT else key[:3]
        merged.setdefault(target, []).extend(group)
    for key, group in merged.items():
        _percentiles(group)
        for e in group:
            e["cohort"] = "|".join(map(str, key))
            e["cohort_n"] = len(group)

    # stratified candidates: image creatives from top + bottom bands, most
    # extreme first per platform x stratum queue. The download step fills the
    # actual sample from these, skipping expired-CDN posts, so selection is
    # download-aware. Band thresholds are env-tunable (STRATA_TOP/STRATA_BOTTOM)
    # so the fine-tune data sweep can widen beyond the default quartiles.
    top_th = float(os.environ.get("STRATA_TOP", "75"))
    bot_th = float(os.environ.get("STRATA_BOTTOM", "25"))
    include_video = os.environ.get("INCLUDE_VIDEO") == "1"
    queues = {}
    for e in eligible:
        if e["cohort_n"] < MIN_COHORT:
            continue
        if e["kind"] == "image":
            qbase = e["platform"]
        elif include_video:
            qbase = f"{e['platform']}-video"
        else:
            continue
        stratum = "top" if e["percentile"] >= top_th else "bottom" if e["percentile"] <= bot_th else None
        if stratum:
            e["stratum"] = stratum
            queues.setdefault(f"{qbase}|{stratum}", []).append(e)
    for q in queues.values():
        q.sort(key=lambda e: abs(e["percentile"] - 50), reverse=True)
    candidates = {k: [e["id"] for e in q] for k, q in sorted(queues.items())}

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump({"posts": eligible, "candidates": candidates, "sample": [],
                   "dropped": dropped}, f, ensure_ascii=False)
    n_img = sum(1 for e in eligible if e["kind"] == "image")
    print(f"eligible {len(eligible)} ({n_img} images) of {len(posts)}; dropped {dropped}")
    print("candidates: " + " ".join(f"{k}={len(v)}" for k, v in candidates.items())
          + f" -> {DATASET_PATH}")


# ---------------------------------------------------------------- download

def _fetch_image(requests, e):
    existing = [p for p in os.listdir(MEDIA_DIR) if p.startswith(e["id"])]
    if existing:
        return os.path.join(MEDIA_DIR, existing[0])
    r = requests.get(e["media_url"], headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
        ctype.split(";")[0].strip())
    if ext is None or len(r.content) < 1024:
        raise ValueError(f"not an image: {ctype or 'unknown'} ({len(r.content)}B)")
    path = os.path.join(MEDIA_DIR, e["id"] + ext)
    with open(path, "wb") as out:
        out.write(r.content)
    return path


def cmd_download():
    """Fill the sample by walking the candidate queues round-robin (platform x
    stratum), skipping posts whose CDN link has expired, until the cap."""
    requests = get_requests()
    with open(DATASET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    os.makedirs(MEDIA_DIR, exist_ok=True)
    cap = int(os.environ.get("SAMPLE_CAP", "60"))
    queues = {k: list(v) for k, v in ds["candidates"].items()}
    sample, tried, fail = list(ds.get("sample") or []), 0, {}
    keys = sorted(queues)
    while len(sample) < cap and any(queues[k] for k in keys):
        for k in keys:
            if not queues[k] or len(sample) >= cap:
                continue
            e = posts[queues[k].pop(0)]
            if e["id"] in sample:
                continue
            if e.get("download_error"):  # known dead from a previous pass
                continue
            tried += 1
            try:
                e["local_path"] = _fetch_image(requests, e)
                sample.append(e["id"])
            except Exception as exc:
                e["download_error"] = str(exc)[:200]
                fail[e["platform"]] = fail.get(e["platform"], 0) + 1
    ds["sample"] = sample
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False)
    by = {}
    for pid in sample:
        e = posts[pid]
        key = f"{e['platform']}|{e['stratum']}"
        by[key] = by.get(key, 0) + 1
    print(f"sample filled: {len(sample)}/{cap} ({tried} attempts; "
          + (f"expired/failed by platform: {fail}" if fail else "no failures") + ")")
    print("  composition: " + " ".join(f"{k}={n}" for k, n in sorted(by.items())))
    if len(sample) < cap:
        print("  (queues exhausted -- consider a fresh Apify scrape to refresh CDN links)")


# ---------------------------------------------------------------- run

def api_url():
    base = require("F1X8_API_URL").rstrip("/")
    if "vercel.app" in base:
        return f"{base}/api/analyze?endpoint=/api/analyze/image"
    return f"{base}/api/analyze/image"


def score_one(requests, url, e):
    with open(e["local_path"], "rb") as f:
        content = f.read()
    name = os.path.basename(e["local_path"])
    for attempt in (1, 2):
        try:
            # lite: judge + CV KPIs only — skips the diagnosis LLM call and
            # perception pass, which calibration never reads
            r = requests.post(url, files={"file": (name, content)},
                              data={"lite": "1"}, timeout=900)
            r.raise_for_status()
            body = r.json()
            if "error" in body:
                raise RuntimeError(body["error"][:200])
            return body
        except Exception as exc:
            if attempt == 2:
                return {"error": str(exc)[:300]}
            time.sleep(10)


def cmd_run():
    requests = get_requests()
    url = api_url()
    with open(DATASET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    todo = []
    for pid in ds["sample"]:
        if not posts[pid].get("local_path"):
            continue
        if os.path.exists(os.path.join(RESULTS_DIR, pid + ".json")):
            continue  # resumable
        todo.append(posts[pid])
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"scoring {len(todo)} creatives via {url}")
    start = time.time()
    from concurrent.futures import ThreadPoolExecutor
    def work(e):
        result = score_one(requests, url, e)
        result.pop("heatmap", None)  # large, not needed for calibration
        with open(os.path.join(RESULTS_DIR, e["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        tag = f"score={result.get('score')}" if "score" not in result.get("error", "") else ""
        print(f"  [{e['platform']}] {e['id'][:8]} {tag or 'ERROR: ' + result.get('error', '')[:80]}")
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(work, todo))
    print(f"done in {time.time() - start:.0f}s -> {RESULTS_DIR}")


# ---------------------------------------------------------------- stats

def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return cov / (sx * sy) if sx and sy else 0.0


def spearman(x, y):
    return pearson(_ranks(x), _ranks(y))


def bootstrap_ci(pairs, stat, n=2000, seed=13):
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = [rng.choice(pairs) for _ in pairs]
        vals.append(stat([p[0] for p in s], [p[1] for p in s]))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def auc(top, bottom):
    """P(random top-quartile creative outscores random bottom-quartile one)."""
    wins = sum(1 if t > b else 0.5 if t == b else 0 for t in top for b in bottom)
    return wins / (len(top) * len(bottom)) if top and bottom else float("nan")


# ---------------------------------------------------------------- report

def cmd_report():
    with open(DATASET_PATH, encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    rows, errors = [], []
    for pid in ds["sample"]:
        e = posts[pid]
        path = os.path.join(RESULTS_DIR, pid + ".json")
        if not e.get("local_path"):
            errors.append((pid, "download: " + e.get("download_error", "?")))
            continue
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        if "score" not in r:
            errors.append((pid, "api: " + r.get("error", "?")))
            continue
        rows.append({**e, "score": r["score"], "funnel": r.get("funnel_stage"),
                     "kpis": {k: v.get("score") for k, v in (r.get("kpis") or {}).items()}})

    if len(rows) < 10:
        sys.exit(f"only {len(rows)} scored creatives — not enough to report (need >=10)")

    pairs = [(r["score"], r["percentile"]) for r in rows]
    rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
    lo, hi = bootstrap_ci(pairs, spearman)
    top = [r["score"] for r in rows if r["stratum"] == "top"]
    bottom = [r["score"] for r in rows if r["stratum"] == "bottom"]
    a = auc(top, bottom)

    def mean(v):
        return sum(v) / len(v) if v else float("nan")

    lines = [
        "# F1X8 calibration report — organic engagement vs Engagement Potential",
        "",
        f"Scored **{len(rows)}** @samsunggulf image creatives "
        f"({len(top)} top-quartile, {len(bottom)} bottom-quartile by cohort-normalized "
        f"engagement percentile). {len(errors)} failures.",
        "",
        "## Headline",
        "",
        f"- **Top-vs-bottom AUC: {a:.2f}** — probability the model scores a "
        "top-quartile creative above a bottom-quartile one (0.5 = chance).",
        f"- Spearman rho (score vs percentile, within stratified sample): "
        f"**{rho:.2f}** (95% CI {lo:.2f} to {hi:.2f}, n={len(rows)}).",
        f"- Mean score: top stratum {mean(top):.2f} vs bottom stratum {mean(bottom):.2f}.",
        "",
        "## Per platform",
        "",
        "| platform | n | Spearman rho | AUC |",
        "|---|---|---|---|",
    ]
    for plat in sorted({r["platform"] for r in rows}):
        sub = [r for r in rows if r["platform"] == plat]
        if len(sub) < 8:
            lines.append(f"| {plat} | {len(sub)} | (n too small) | |")
            continue
        srho = spearman([r["score"] for r in sub], [r["percentile"] for r in sub])
        sauc = auc([r["score"] for r in sub if r["stratum"] == "top"],
                   [r["score"] for r in sub if r["stratum"] == "bottom"])
        lines.append(f"| {plat} | {len(sub)} | {srho:.2f} | {sauc:.2f} |")

    lines += ["", "## Per KPI", "",
              "KPI sets differ by funnel stage; each row uses the creatives where that KPI was surfaced.",
              "", "| kpi | n | Spearman rho |", "|---|---|---|"]
    kpi_ids = sorted({k for r in rows for k in r["kpis"]})
    for kid in kpi_ids:
        sub = [r for r in rows if r["kpis"].get(kid) is not None]
        if len(sub) < 8:
            continue
        krho = spearman([r["kpis"][kid] for r in sub], [r["percentile"] for r in sub])
        lines.append(f"| {kid} | {len(sub)} | {krho:.2f} |")

    funnel = {}
    for r in rows:
        funnel[r["funnel"]] = funnel.get(r["funnel"], 0) + 1
    lines += ["", "## Funnel stage distribution", "",
              " · ".join(f"{k}: {v}" for k, v in sorted(funnel.items())),
              "", "## Failures", ""]
    lines += [f"- `{pid[:8]}` {msg}" for pid, msg in errors] or ["(none)"]
    lines += [
        "", "## Caveats", "",
        "- Organic engagement is a *proxy* for paid performance: no targeting, no "
        "spend, algorithm-driven reach. Read direction and discrimination (AUC), "
        "not absolute calibration.",
        "- Sample is stratified to quartile extremes, so Spearman on this sample "
        "overstates full-distribution correlation; AUC is the honest headline.",
        "- The deployed backend is the median-of-3 ensemble judge (deployed "
        "2026-07-28, before this scoring run). Residual judge noise still "
        "attenuates correlations, but less than the single-judge build would.",
        "- Labels are cohort-normalized (platform x kind x basis x quarter, merged "
        f"when n<{MIN_COHORT}) — but confounds like posting time and celebrity "
        "presence remain.",
        "- Many Supabase 'image' rows are actually reels (media_type reflects the "
        "thumbnail): ~56% of the extreme-quartile candidates scraped for URL "
        "refresh were videos. Reels are excluded from the scored sample, but they "
        "contaminate the image cohorts' percentile ranks, and top-stratum images "
        "are specifically images that out-competed reels.",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"report -> {REPORT_PATH}")
    print(f"\nHeadline: AUC {a:.2f}, Spearman {rho:.2f} (CI {lo:.2f}..{hi:.2f}), n={len(rows)}")


COMMANDS = {"export": cmd_export, "build": cmd_build, "download": cmd_download,
            "run": cmd_run, "report": cmd_report}


def main():
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "all":
        for name in ("export", "build", "download", "run", "report"):
            print(f"== {name} ==")
            COMMANDS[name]()
    elif cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
