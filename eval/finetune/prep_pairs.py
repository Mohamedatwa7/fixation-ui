"""Build the pairwise-ranking manifest for the engagement ranker (step 3 of
the fine-tune plan).

Splits the scored calibration sample into:
  train   — the anchor-design set (the 60 creatives whose judge results were
            used to write the prompt anchors; identified as the ids present in
            data/results-preanchor/)
  holdout — every later-sampled creative with a downloaded image (never used
            for anchor design; reserved for evaluation only)

Labels are the cohort-normalized engagement percentiles and top/bottom
stratum from dataset.json. Pairs are (top-stratum image, bottom-stratum
image) within a split — the ranker learns P(top outranks bottom).

    python eval/finetune/prep_pairs.py   ->  eval/finetune/data/manifest.json
"""

import json
import os
import sys

FT_DIR = os.path.dirname(os.path.abspath(__file__))
CAL_DATA = os.path.normpath(os.path.join(FT_DIR, "..", "calibration", "data"))
OUT_PATH = os.path.join(FT_DIR, "data", "manifest.json")


def main():
    with open(os.path.join(CAL_DATA, "dataset.json"), encoding="utf-8") as f:
        ds = json.load(f)
    posts = {e["id"]: e for e in ds["posts"]}
    design = set()
    pre = os.path.join(CAL_DATA, "results-preanchor")
    if os.path.isdir(pre):
        design = {fn[:-5] for fn in os.listdir(pre) if fn.endswith(".json")}

    splits = {"train": [], "holdout": []}
    for pid in ds["sample"]:
        e = posts[pid]
        path = e.get("local_path")
        if not path or not os.path.exists(path):
            continue
        split = "train" if pid in design else "holdout"
        splits[split].append({
            "id": pid, "image": os.path.abspath(path),
            "stratum": e["stratum"], "percentile": e["percentile"],
            "platform": e["platform"],
        })

    for name, items in splits.items():
        top = sum(1 for i in items if i["stratum"] == "top")
        print(f"{name}: {len(items)} images ({top} top / {len(items) - top} bottom)")
    if len(splits["train"]) < 20:
        sys.exit("train split too small -- is results-preanchor/ present?")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(splits, f, ensure_ascii=False, indent=1)
    print(f"manifest -> {OUT_PATH}")


if __name__ == "__main__":
    main()
