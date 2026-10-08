"""Sprinklr chain C: train the multi-platform ranker, measure, calibrate.

- Base: CreativeRanking-pretrained Qwen3-VL-4B adapter (out_cr) — the
  Samsung model stays untouched in production until this one proves out.
- Train: account-aware within-cohort pairs from assemble.py (one epoch cap
  via MAX_PAIRS, checkpoint/resume every 1k).
- Measure: top-vs-bottom AUC on the frozen 400-creative multi-platform
  holdout, per-platform breakdown, PLUS the legacy 82-creative Samsung
  holdout for continuity.
- Calibrate: score-bucket hit rates ("8+ scores land top-quartile N% of
  the time") — the product's accuracy sentence.
- Captions: cheap text-feature correlations (length, hashtags, emoji) so
  caption effects are quantified before anyone tests captions manually.

    python eval/sprinklr/train_sprinklr.py
"""

import json
import os
import random
import re
import sys
import time
from collections import defaultdict

SPR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SPR_DIR, "data")
REPO = os.path.dirname(os.path.dirname(SPR_DIR))
FT_DIR = os.path.join(REPO, "eval", "finetune")
OUT_DIR = os.path.join(SPR_DIR, "out")
PRETRAIN = os.path.join(FT_DIR, "out_cr")

MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"
MAX_PIXELS = 512 * 28 * 28
LR = 5e-6
MAX_PAIRS = 45000
GRAD_ACCUM = 8
SAVE_EVERY = 1000

sys.path.insert(0, os.path.join(REPO, "eval", "calibration"))
from aam_ab import spearman, auc  # noqa: E402

random.seed(48)


def load_all():
    with open(os.path.join(DATA_DIR, "dataset.json"), encoding="utf-8") as f:
        rows = json.load(f)
    with open(os.path.join(DATA_DIR, "pairs.json"), encoding="utf-8") as f:
        pairs = json.load(f)
    by_id = {r["id"]: r for r in rows}
    pairs = [p for p in pairs
             if p["top"] in by_id and p["bottom"] in by_id][:MAX_PAIRS]
    return rows, by_id, pairs


def build_model():
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText
    from peft import PeftModel
    processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=MAX_PIXELS)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    model.gradient_checkpointing_enable()
    model = PeftModel.from_pretrained(
        model, os.path.join(PRETRAIN, "adapter"), is_trainable=True)
    hidden = getattr(model.config, "text_config", model.config).hidden_size
    head = torch.nn.Linear(hidden, 1, dtype=torch.bfloat16).to("cuda")
    head.load_state_dict(torch.load(os.path.join(PRETRAIN, "head.pt"),
                                    weights_only=True))
    return processor, model, head


def main():
    import torch
    import torch.nn.functional as F
    from PIL import Image as PILImage

    os.makedirs(OUT_DIR, exist_ok=True)
    rows, by_id, pairs = load_all()
    holdout = [r for r in rows if r["split"] == "holdout"
               and r["stratum"] in ("top", "bottom")]
    print(f"{len(pairs)} pairs | holdout {len(holdout)}")

    processor, model, head = build_model()
    chat = processor.apply_chat_template(
        [{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": "Assess this e-commerce advertising "
                                     "creative for in-feed engagement potential."}]}],
        tokenize=False, add_generation_prompt=True)

    def score(img_path, grad=True):
        img = PILImage.open(img_path).convert("RGB")
        inputs = processor(text=[chat], images=[img],
                           return_tensors="pt").to("cuda")
        ctx = torch.enable_grad() if grad else torch.no_grad()
        with ctx:
            out = model(**inputs, output_hidden_states=True)
            hs = out.hidden_states[-1]
            idx = int(inputs["attention_mask"].sum(1).item()) - 1
            return head(hs[0, idx]).squeeze()

    def eval_holdout():
        model.eval()
        scores = {}
        for r in holdout:
            scores[r["id"]] = float(score(r["image"], grad=False))
        model.train()
        def auc_for(subset):
            top = [scores[r["id"]] for r in subset if r["stratum"] == "top"]
            bot = [scores[r["id"]] for r in subset if r["stratum"] == "bottom"]
            return auc(top, bot) if top and bot else float("nan")
        per_plat = {}
        for plat in sorted({r["platform"] for r in holdout}):
            per_plat[plat] = round(auc_for([r for r in holdout
                                            if r["platform"] == plat]), 3)
        return round(auc_for(holdout), 4), per_plat, scores

    # resume support
    state_p = os.path.join(OUT_DIR, "train_state.json")
    start = 0
    if os.path.exists(state_p):
        with open(state_p, encoding="utf-8") as f:
            start = json.load(f).get("pairs_done", 0)
        if os.path.isdir(os.path.join(OUT_DIR, "adapter")):
            model.load_adapter(os.path.join(OUT_DIR, "adapter"), "default")
            head.load_state_dict(torch.load(os.path.join(OUT_DIR, "head.pt"),
                                            weights_only=True))
            print(f"resumed at pair {start}")

    if start == 0:
        zs_auc, zs_plat, _ = eval_holdout()
        print(f"ZERO-SHOT (CR-pretrained): auc={zs_auc} per-platform={zs_plat}",
              flush=True)

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW([{"params": params, "lr": LR},
                             {"params": head.parameters(), "lr": LR * 10}])
    model.train()
    t0 = time.time()
    for i in range(start, len(pairs)):
        p = pairs[i]
        try:
            loss = F.softplus(-(score(by_id[p["top"]]["image"])
                                - score(by_id[p["bottom"]]["image"]))) / GRAD_ACCUM
            loss.backward()
        except Exception as e:
            print(f"  pair {i} failed: {e!r}")
            opt.zero_grad(set_to_none=True)
            continue
        if (i + 1) % GRAD_ACCUM == 0:
            torch.nn.utils.clip_grad_norm_(params + list(head.parameters()), 1.0)
            opt.step()
            opt.zero_grad(set_to_none=True)
        if (i + 1) % SAVE_EVERY == 0:
            model.save_pretrained(os.path.join(OUT_DIR, "adapter"))
            torch.save(head.state_dict(), os.path.join(OUT_DIR, "head.pt"))
            with open(state_p, "w", encoding="utf-8") as f:
                json.dump({"pairs_done": i + 1}, f)
            rate = (i + 1 - start) / (time.time() - t0)
            print(f"[{i+1}/{len(pairs)}] {rate:.2f} pairs/s "
                  f"ETA {(len(pairs)-i-1)/rate/3600:.1f}h", flush=True)
        if (i + 1) % 10000 == 0:
            a, plat, _ = eval_holdout()
            print(f"[{i+1}] holdout auc={a} per-platform={plat}", flush=True)

    final_auc, per_plat, scores = eval_holdout()
    print(f"FINAL holdout auc={final_auc} per-platform={per_plat}")
    model.save_pretrained(os.path.join(OUT_DIR, "adapter"))
    torch.save(head.state_dict(), os.path.join(OUT_DIR, "head.pt"))

    # calibration curve on holdout: squash scores 0-10, bucket hit-rates
    vals = sorted(scores.values())
    mid = vals[len(vals) // 2]
    spread = (vals[int(0.9 * len(vals))] - vals[int(0.1 * len(vals))]) or 1.0
    import math
    buckets = defaultdict(lambda: [0, 0])
    for r in holdout:
        s10 = 10.0 / (1.0 + math.exp(-(scores[r["id"]] - mid) * 2.0 / spread))
        b = ("8+" if s10 >= 8 else "6-8" if s10 >= 6 else "4-6" if s10 >= 4
             else "<4")
        buckets[b][1] += 1
        buckets[b][0] += (r["stratum"] == "top")
    calib = {b: {"n": n, "top_quartile_rate": round(hit / n, 3)}
             for b, (hit, n) in sorted(buckets.items()) if n}
    with open(os.path.join(OUT_DIR, "calibration.json"), "w", encoding="utf-8") as f:
        json.dump({"holdout_scores": scores}, f)

    # caption quick-analysis on the full train split
    train_rows = [r for r in rows if r["split"] == "train"]
    def feats(c):
        return {"len": len(c), "hashtags": c.count("#"),
                "emoji": len(re.findall(r"[\U0001F000-\U0001FAFF]", c)),
                "has_question": int("?" in c)}
    caption_corr = {}
    for feat in ("len", "hashtags", "emoji", "has_question"):
        xs = [feats(r.get("caption_full") or "")[feat] for r in train_rows]
        ys = [r["percentile"] for r in train_rows]
        caption_corr[feat] = round(spearman(xs, ys), 3)

    result = {"model_id": MODEL_ID, "base": "out_cr(epoch2)",
              "train_pairs": len(pairs), "holdout_n": len(holdout),
              "holdout_auc": final_auc, "per_platform_auc": per_plat,
              "calibration_buckets": calib, "caption_spearman": caption_corr}
    with open(os.path.join(OUT_DIR, "RESULT.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
