"""Rematch recovered Apify items to labeled posts (no re-scrape needed).

First pass lost ~2.1k items to naive URL matching: IG items key on
shortCode, and the FB posts-scraper returns raw photo NODES (image.uri,
facebookUrl=photo.php?fbid=...) alongside post wrappers (media[]). This
rebuilds media_meta.json from data/apify_raw/all_items.json with proper
keys, then fetch_media.py images downloads the rest.
"""

import json
import os
import re
from urllib.parse import urlparse, parse_qs

SPR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SPR_DIR, "data")
META = os.path.join(DATA_DIR, "media_meta.json")

SHORT = re.compile(r"/(?:reel|p|tv)/([\w-]+)")


def norm(u):
    return (u or "").split("?")[0].rstrip("/").replace("http://", "https://")


def fbid(u):
    q = parse_qs(urlparse(u or "").query)
    return (q.get("fbid") or q.get("story_fbid") or [None])[0]


def main():
    with open(os.path.join(DATA_DIR, "labels.json"), encoding="utf-8") as f:
        posts = json.load(f)
    with open(META, encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(DATA_DIR, "apify_raw", "all_items.json"),
              encoding="utf-8") as f:
        items = json.load(f)

    ig_by_code, fb_by_url, fb_by_id = {}, {}, {}
    for it in items:
        if it.get("shortCode"):
            ig_by_code[it["shortCode"]] = it
        fu = it.get("facebookUrl") or it.get("url")
        if it.get("pageName") or it.get("facebookUrl"):
            if fu:
                fb_by_url[norm(fu)] = it
                fid = fbid(fu)
                if fid:
                    fb_by_id[fid] = it

    fixed = {"INSTAGRAM": 0, "FBPAGE": 0}
    for p in posts:
        url = p["url"]
        cur = meta.get(url) or {}
        if cur.get("file") or cur.get("media_url"):
            continue
        if p["platform"] == "INSTAGRAM":
            m = SHORT.search(url)
            it = ig_by_code.get(m.group(1)) if m else None
            if it:
                meta[url] = {
                    "account": it.get("ownerUsername"),
                    "caption_full": (it.get("caption") or "")[:2000],
                    "media_url": it.get("displayUrl"),
                    "video_url": it.get("videoUrl"),
                }
                fixed["INSTAGRAM"] += 1
        elif p["platform"] == "FBPAGE":
            it = fb_by_url.get(norm(url)) or (fb_by_id.get(fbid(url))
                                              if fbid(url) else None)
            if not it:
                continue
            murl = None
            if it.get("media"):
                for mm in it["media"]:
                    murl = ((mm.get("photo_image") or {}).get("uri")
                            or (mm.get("large_share_image") or {}).get("uri")
                            or (mm.get("thumbnail") if isinstance(mm.get("thumbnail"), str)
                                else (mm.get("thumbnail") or {}).get("uri"))
                            or murl)
            if not murl and isinstance(it.get("image"), dict):
                murl = it["image"].get("uri")
            if not murl and isinstance(it.get("image"), str):
                murl = it["image"]
            if murl:
                meta[url] = {
                    "account": it.get("pageName")
                               or (it.get("owner") or {}).get("name"),
                    "caption_full": (it.get("text")
                                     or it.get("accessibility_caption") or "")[:2000],
                    "media_url": murl,
                }
                fixed["FBPAGE"] += 1
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    print("rematched:", fixed)


if __name__ == "__main__":
    main()
