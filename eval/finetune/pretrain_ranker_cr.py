"""Pretrain the pairwise engagement ranker on Alibaba CreativeRanking.

Within-product (high-CTR, low-CTR) creative pairs isolate the creative's
own contribution to clicks — the exact signal the production LoRA ranker
models, at ~2,400x the scale of the 142-image Samsung set. This produces a
pretrained adapter + scoring head; fine-tuning on the Samsung pairs stays a
separate step (eval/finetune/train_ranker_modal.py lineage).

Runs locally on the RTX 5090 in its own venv (.venv-train — newer
transformers than the serving stack):

    python pretrain_ranker_cr.py pairs     # within-product pair manifest
    python pretrain_ranker_cr.py extract   # pull pair images from images.zip
    python pretrain_ranker_cr.py train     # LoRA r=16 + scalar head (long)

Checkpoints + holdout pair-accuracy land in out_cr/. Resumable: train
saves every SAVE_EVERY pairs and restarts from the last checkpoint.
"""

import json
import os
import random
import sys
import zipfile
from collections import defaultdict

FT_DIR = os.path.dirname(os.path.abspath(__file__))
CR_DIR = r"D:\datasets\CreativeRanking"
LIST_DIR = os.path.join(CR_DIR, "list_extracted", "list")
IMAGES_ZIP = os.path.join(CR_DIR, "images.zip")
IMG_DIR = os.path.join(CR_DIR, "pair_images")
OUT_DIR = os.path.join(FT_DIR, "out_cr")
PAIRS_PATH = os.path.join(OUT_DIR, "pairs.json")

MODEL_ID = os.environ.get("RANKER_BASE", "Qwen/Qwen3-VL-4B-Instruct")
MIN_SHOWS = 100
MIN_GAP = 50.0            # within-product percentile gap for a training pair
MAX_PAIRS = 40000
HOLDOUT_PRODUCTS = 1500   # whole products held out -> no leakage
MAX_PIXELS = 512 * 28 * 28
LR = 1e-5
SAVE_EVERY = 1000
SMOOTH_A, SMOOTH_B = 1.0, 200.0

random.seed(48)


def cmd_pairs():
    os.makedirs(OUT_DIR, exist_ok=True)
    agg = {}
    for name in ("train_data_list.txt", "val_data_list.txt", "test_data_list.txt"):
        with open(os.path.join(LIST_DIR, name), encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) != 5:
                    continue
                prod, img, _, shows, clicks = p
                rec = agg.setdefault(img, [prod, 0, 0])
                rec[1] += int(shows)
                rec[2] += int(clicks)
    pool_ctr = (sum(r[2] for r in agg.values())
                / max(1, sum(r[1] for r in agg.values())))
    by_prod = defaultdict(list)
    for img, (prod, shows, clicks) in agg.items():
        if shows >= MIN_SHOWS:
            ctr_s = (clicks + SMOOTH_A * pool_ctr * SMOOTH_B) / (shows + SMOOTH_B)
            by_prod[prod].append((img, ctr_s))
    pairs = []
    for prod, rows in by_prod.items():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: r[1])
        n = len(rows)
        lo_img, lo_ctr = rows[0]
        hi_img, hi_ctr = rows[-1]
        gap = 100.0 * (n - 1) / n if n > 1 else 0   # top vs bottom rank gap
        # percentile positions of extremes: (0.5/n)*100 and ((n-0.5)/n)*100
        gap = 100.0 * (n - 1) / n
        if gap < MIN_GAP or hi_ctr <= lo_ctr:
            continue
        pairs.append({"product": prod, "top": hi_img, "bottom": lo_img,
                      "ctr_gap": round(hi_ctr - lo_ctr, 6), "n_creatives": n})
    # Prefer pairs with the largest CTR gaps (cleanest supervision).
    pairs.sort(key=lambda p: -p["ctr_gap"])
    pairs = pairs[:MAX_PAIRS]
    random.shuffle(pairs)
    prods = sorted({p["product"] for p in pairs})
    random.shuffle(prods)
    holdout = set(prods[:HOLDOUT_PRODUCTS])
    for p in pairs:
        p["split"] = "holdout" if p["product"] in holdout else "train"
    with open(PAIRS_PATH, "w", encoding="utf-8") as f:
        json.dump(pairs, f)
    n_h = sum(1 for p in pairs if p["split"] == "holdout")
    print(f"{len(pairs)} pairs ({n_h} holdout) -> {PAIRS_PATH}")


def cmd_extract():
    with open(PAIRS_PATH, encoding="utf-8") as f:
        pairs = json.load(f)
    os.makedirs(IMG_DIR, exist_ok=True)
    want = set()
    for p in pairs:
        for img in (p["top"], p["bottom"]):
            if not os.path.exists(os.path.join(IMG_DIR, img)):
                want.add(img)
    print(f"extracting {len(want)} images")
    if not want:
        return
    with zipfile.ZipFile(IMAGES_ZIP) as z:
        by_base = {}
        for n in z.namelist():
            b = n.rsplit("/", 1)[-1]
            if b in want:
                by_base[b] = n
        done = 0
        for base, member in by_base.items():
            with z.open(member) as src, \
                    open(os.path.join(IMG_DIR, base), "wb") as dst:
                dst.write(src.read())
            done += 1
            if done % 5000 == 0:
                print(f"  {done}/{len(by_base)}", flush=True)
    print("extract complete")


def _load_model(device):
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText
    from peft import LoraConfig, get_peft_model
    processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=MAX_PIXELS)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map=device)
    model.gradient_checkpointing_enable()
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    hidden = getattr(model.config, "text_config", model.config).hidden_size
    head = torch.nn.Linear(hidden, 1, dtype=torch.bfloat16).to(device)
    return processor, model, head


def cmd_train():
    import time
    import torch
    import torch.nn.functional as F
    from PIL import Image as PILImage

    dev = "cuda"
    with open(PAIRS_PATH, encoding="utf-8") as f:
        pairs = json.load(f)
    have = lambda p: (os.path.exists(os.path.join(IMG_DIR, p["top"]))
                      and os.path.exists(os.path.join(IMG_DIR, p["bottom"])))
    train = [p for p in pairs if p["split"] == "train" and have(p)]
    hold = [p for p in pairs if p["split"] == "holdout" and have(p)]
    print(f"train pairs: {len(train)}  holdout pairs: {len(hold)}")

    processor, model, head = _load_model(dev)
    prompt_text = ("Assess this e-commerce advertising creative for in-feed "
                   "engagement potential.")
    messages = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": prompt_text}]}]
    chat_text = processor.apply_chat_template(messages, tokenize=False,
                                              add_generation_prompt=True)

    def score(img_name, grad=True):
        img = PILImage.open(os.path.join(IMG_DIR, img_name)).convert("RGB")
        inputs = processor(text=[chat_text], images=[img],
                           return_tensors="pt").to(dev)
        ctx = torch.enable_grad() if grad else torch.no_grad()
        with ctx:
            out = model(**inputs, output_hidden_states=True)
            hs = out.hidden_states[-1]
            idx = int(inputs["attention_mask"].sum(1).item()) - 1
            return head(hs[0, idx]).squeeze()

    params = [p for p in model.parameters() if p.requires_grad] + list(head.parameters())
    opt = torch.optim.AdamW(params, lr=LR)
    start = 0
    ckpt_meta = os.path.join(OUT_DIR, "train_state.json")
    if os.path.exists(ckpt_meta):
        with open(ckpt_meta, encoding="utf-8") as f:
            start = json.load(f).get("pairs_done", 0)
        if start and os.path.isdir(os.path.join(OUT_DIR, "adapter")):
            print(f"resuming from pair {start}")
            model.load_adapter(os.path.join(OUT_DIR, "adapter"), "default")
            head.load_state_dict(torch.load(os.path.join(OUT_DIR, "head.pt"),
                                            weights_only=True))

    def save(n_done):
        model.save_pretrained(os.path.join(OUT_DIR, "adapter"))
        torch.save(head.state_dict(), os.path.join(OUT_DIR, "head.pt"))
        with open(ckpt_meta, "w", encoding="utf-8") as f:
            json.dump({"pairs_done": n_done, "model_id": MODEL_ID}, f)

    def holdout_acc(sample_n=400):
        model.eval()
        sub = hold[:sample_n]
        wins = 0
        for p in sub:
            if score(p["top"], grad=False) > score(p["bottom"], grad=False):
                wins += 1
        model.train()
        return wins / max(1, len(sub))

    GRAD_ACCUM = 8
    t0 = time.time()
    losses = []
    model.train()
    for i in range(start, len(train)):
        p = train[i]
        try:
            s_top = score(p["top"])
            s_bot = score(p["bottom"])
            loss = F.softplus(-(s_top - s_bot)) / GRAD_ACCUM   # -log sigmoid(diff)
            loss.backward()
            losses.append(float(loss) * GRAD_ACCUM)
        except Exception as e:
            print(f"  pair {i} failed: {e!r}")
            opt.zero_grad(set_to_none=True)
            continue
        if (i + 1) % GRAD_ACCUM == 0:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            opt.zero_grad(set_to_none=True)
        if (i + 1) % SAVE_EVERY == 0:
            save(i + 1)
            rate = (i + 1 - start) / (time.time() - t0)
            eta_h = (len(train) - i - 1) / rate / 3600
            avg = sum(losses[-SAVE_EVERY:]) / max(1, len(losses[-SAVE_EVERY:]))
            print(f"[{i+1}/{len(train)}] loss={avg:.4f} "
                  f"{rate:.2f} pairs/s ETA {eta_h:.1f}h", flush=True)
        if (i + 1) % 10000 == 0:
            acc = holdout_acc()
            print(f"[{i+1}] holdout pair-accuracy: {acc:.4f}", flush=True)
    save(len(train))
    acc = holdout_acc(len(hold))
    print(f"FINAL holdout pair-accuracy ({len(hold)} pairs): {acc:.4f}")
    with open(os.path.join(OUT_DIR, "RESULT.json"), "w", encoding="utf-8") as f:
        json.dump({"model_id": MODEL_ID, "train_pairs": len(train),
                   "holdout_pairs": len(hold), "holdout_accuracy": acc}, f)


if __name__ == "__main__":
    {"pairs": cmd_pairs, "extract": cmd_extract,
     "train": cmd_train}[sys.argv[1] if len(sys.argv) > 1 else "pairs"]()
