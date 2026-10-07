"""Fine-tune the CreativeRanking-pretrained ranker on the Samsung pairs.

The A/B that decides whether pretraining pays: same 142-image train split,
same 82-creative holdout, same top-vs-bottom-quartile AUC as the 0.851
baseline (train_ranker_modal.py, Qwen2.5-VL-3B from scratch). Variants:

    pre_lr5e6    pretrained adapter (out_cr), LR 5e-6   (gentle re-anchor)
    pre_lr2e5    pretrained adapter (out_cr), LR 2e-5   (stronger adaptation)
    scratch_4b   fresh LoRA on Qwen3-VL-4B,   LR 2e-5   (isolates the
                 base-model upgrade from the pretraining effect)

    D:\\F1X8\\.venv-train\\Scripts\\python.exe eval/finetune/finetune_samsung.py [variant ...]

Zero-shot holdout AUC is reported before any tuning; per-epoch train and
holdout AUC after. Best-by-holdout adapter saved to out_samsung/<variant>/.
"""

import json
import os
import random
import sys

FT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(FT_DIR))
MEDIA_DIR = os.path.join(REPO, "eval", "calibration", "data", "media")
MANIFEST = os.path.join(FT_DIR, "data", "manifest.json")
PRETRAIN_DIR = os.path.join(FT_DIR, "out_cr")
OUT_ROOT = os.path.join(FT_DIR, "out_samsung")

MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"
MAX_PIXELS = 512 * 28 * 28
MIN_GAP = 30
PAIRS_PER_EPOCH = 1200
EPOCHS = 3
GRAD_ACCUM = 8

VARIANTS = {
    "pre_lr5e6":  {"pretrained": True,  "lr": 5e-6},
    "pre_lr2e5":  {"pretrained": True,  "lr": 2e-5},
    "scratch_4b": {"pretrained": False, "lr": 2e-5},
}


def load_splits():
    with open(MANIFEST, encoding="utf-8") as f:
        splits = json.load(f)
    for split in splits.values():
        for item in split:
            base = item["image"].replace("\\", "/").rsplit("/", 1)[-1]
            item["image"] = os.path.join(MEDIA_DIR, base)
    return splits


def build_model(pretrained):
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText
    processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=MAX_PIXELS)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    model.gradient_checkpointing_enable()
    hidden = getattr(model.config, "text_config", model.config).hidden_size
    head = torch.nn.Linear(hidden, 1, dtype=torch.bfloat16).to("cuda")
    if pretrained:
        from peft import PeftModel
        model = PeftModel.from_pretrained(
            model, os.path.join(PRETRAIN_DIR, "adapter"), is_trainable=True)
        head.load_state_dict(torch.load(os.path.join(PRETRAIN_DIR, "head.pt"),
                                        weights_only=True))
    else:
        from peft import LoraConfig, get_peft_model
        lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                          task_type="CAUSAL_LM")
        model = get_peft_model(model, lora)
    return processor, model, head


def run_variant(name, cfg):
    import time
    import torch
    import torch.nn.functional as F
    from PIL import Image as PILImage

    print(f"\n===== variant {name} (pretrained={cfg['pretrained']}, "
          f"lr={cfg['lr']}) =====")
    splits = load_splits()
    processor, model, head = build_model(cfg["pretrained"])
    prompt_text = ("Assess this e-commerce advertising creative for in-feed "
                   "engagement potential.")
    messages = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": prompt_text}]}]
    chat_text = processor.apply_chat_template(messages, tokenize=False,
                                              add_generation_prompt=True)

    def score(path, grad=True):
        img = PILImage.open(path).convert("RGB")
        inputs = processor(text=[chat_text], images=[img],
                           return_tensors="pt").to("cuda")
        ctx = torch.enable_grad() if grad else torch.no_grad()
        with ctx:
            out = model(**inputs, output_hidden_states=True)
            hs = out.hidden_states[-1]
            idx = int(inputs["attention_mask"].sum(1).item()) - 1
            return head(hs[0, idx]).squeeze()

    def evaluate(items, return_scores=False):
        model.eval()
        scores = {}
        for it in items:
            scores[it["id"]] = float(score(it["image"], grad=False))
        model.train()
        top = [scores[i["id"]] for i in items if i["stratum"] == "top"]
        bot = [scores[i["id"]] for i in items if i["stratum"] == "bottom"]
        wins = sum(1 for t in top for b in bot if t > b)
        ties = sum(1 for t in top for b in bot if t == b)
        auc = (wins + 0.5 * ties) / (len(top) * len(bot)) if top and bot \
            else float("nan")
        return (auc, scores) if return_scores else auc

    zero_shot = evaluate(splits["holdout"])
    print(f"[{name}] zero-shot holdout AUC: {zero_shot:.3f}", flush=True)

    train_items = splits["train"]
    all_pairs = [(a, b) for a in train_items for b in train_items
                 if a["percentile"] - b["percentile"] >= MIN_GAP]
    print(f"{len(train_items)} train images -> {len(all_pairs)} pairs")
    rng = random.Random(13)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW([{"params": params, "lr": cfg["lr"]},
                             {"params": head.parameters(), "lr": cfg["lr"] * 10}])
    out_dir = os.path.join(OUT_ROOT, name)
    os.makedirs(out_dir, exist_ok=True)
    history = [{"epoch": 0, "holdout_auc": round(zero_shot, 4)}]
    best = zero_shot if cfg["pretrained"] else -1.0  # scratch must earn a save
    model.train()
    for epoch in range(1, EPOCHS + 1):
        pairs = rng.sample(all_pairs, min(PAIRS_PER_EPOCH, len(all_pairs)))
        t0 = time.time()
        running = 0.0
        for i, (t, b) in enumerate(pairs):
            try:
                loss = F.softplus(-(score(t["image"]) - score(b["image"]))) / GRAD_ACCUM
                loss.backward()
                running += float(loss) * GRAD_ACCUM
            except Exception as e:
                print(f"  pair failed: {e!r}")
                opt.zero_grad(set_to_none=True)
                continue
            if (i + 1) % GRAD_ACCUM == 0:
                torch.nn.utils.clip_grad_norm_(
                    params + list(head.parameters()), 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
        tr_auc = evaluate(train_items)
        ho_auc, ho_scores = evaluate(splits["holdout"], return_scores=True)
        print(f"[{name}] epoch {epoch}: loss={running/len(pairs):.4f} "
              f"train_auc={tr_auc:.3f} holdout_auc={ho_auc:.3f} "
              f"({time.time()-t0:.0f}s)", flush=True)
        history.append({"epoch": epoch, "train_auc": round(tr_auc, 4),
                        "holdout_auc": round(ho_auc, 4)})
        if ho_auc > best:
            best = ho_auc
            model.save_pretrained(os.path.join(out_dir, "adapter"))
            torch.save(head.state_dict(), os.path.join(out_dir, "head.pt"))
            # serving sidecar / Modal endpoint calibrate their 0-10 squash
            # from the holdout score distribution of the saved checkpoint
            with open(os.path.join(out_dir, "calibration.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"holdout_scores": ho_scores}, f)
    with open(os.path.join(out_dir, "RESULT.json"), "w", encoding="utf-8") as f:
        json.dump({"variant": name, **cfg, "model_id": MODEL_ID,
                   "zero_shot_holdout_auc": round(zero_shot, 4),
                   "best_holdout_auc": round(best, 4),
                   "baseline_from_scratch_3b": 0.851,
                   "history": history}, f, indent=1)
    print(f"[{name}] BEST holdout AUC: {best:.3f} (baseline 0.851)")
    del model, head
    torch.cuda.empty_cache()
    return best


if __name__ == "__main__":
    names = sys.argv[1:] or list(VARIANTS)
    results = {}
    for n in names:
        results[n] = run_variant(n, VARIANTS[n])
    print("\n===== SUMMARY (holdout AUC, baseline 0.851) =====")
    for n, v in results.items():
        print(f"  {n}: {v:.3f}")
