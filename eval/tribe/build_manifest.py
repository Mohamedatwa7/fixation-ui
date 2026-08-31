"""Build the TRIBE v2 extraction manifest from the calibration dataset.

Items: every labeled image with a local media file, plus every reel that the
video pipeline already scored (results-video/) — those are re-fetched by URL
inside the Modal harness since IG CDN links expire.

Usage: python eval/tribe/build_manifest.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "calibration", "data")


def main():
    posts = json.load(open(os.path.join(DATA, "dataset.json"), encoding="utf-8"))["posts"]
    media = {f.split(".")[0]: f for f in os.listdir(os.path.join(DATA, "media"))}
    scored_videos = {f.split(".")[0] for f in os.listdir(os.path.join(DATA, "results-video"))}

    items = []
    for p in posts:
        base = {"id": p["id"], "percentile": p.get("percentile"), "cohort": p.get("cohort")}
        if p["kind"] == "image" and p["id"] in media:
            items.append({**base, "kind": "image",
                          "path": os.path.join("eval", "calibration", "data", "media", media[p["id"]])})
        elif p["kind"] == "video" and p["id"] in scored_videos:
            items.append({**base, "kind": "video", "url": p["post_url"]})

    out = os.path.join(HERE, "manifest.json")
    json.dump(items, open(out, "w", encoding="utf-8"), indent=1)
    n_img = sum(1 for i in items if i["kind"] == "image")
    print(f"wrote {out}: {len(items)} items ({n_img} images, {len(items) - n_img} videos)")


if __name__ == "__main__":
    main()
