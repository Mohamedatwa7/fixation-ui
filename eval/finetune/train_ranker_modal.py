"""Qwen2.5-VL LoRA pairwise engagement ranker — first training run (step 3
of the fine-tune plan).

Trains on (top, bottom) stratum pairs from the anchor-design split and
evaluates ranking quality on the untouched holdout split. The target is NOT
to beat the judge yet (n=60 train images is proof-of-concept scale); it is to
stand up the full pipeline: data -> GPU training on Modal -> honest holdout
AUC, with the adapter saved to a Modal volume for iteration.

    python -m modal run eval/finetune/train_ranker_modal.py

Outputs eval/finetune/data/train_metrics.json locally and saves the LoRA
adapter + scoring head to the Modal volume `fixation-ranker`.
"""

import json
import os

import modal

FT_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.normpath(os.path.join(FT_DIR, "..", "calibration", "data", "media"))
MANIFEST = os.path.join(FT_DIR, "data", "manifest.json")

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
MAX_PIXELS = 512 * 28 * 28   # bound visual tokens so a pair fits on A10G
PAIRS_PER_EPOCH = 600
EPOCHS = 2
GRAD_ACCUM = 8

app = modal.App("fixation-ranker-train")
hf_cache = modal.Volume.from_name("fixation-ranker-hf", create_if_missing=True)
out_vol = modal.Volume.from_name("fixation-ranker", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.4.0", "transformers==4.51.3", "peft==0.13.2",
                 "accelerate==1.1.1", "pillow")
    .env({"HF_HOME": "/hf"})
    .add_local_dir(MEDIA_DIR, remote_path="/media")
    .add_local_file(MANIFEST, remote_path="/manifest.json")
)


@app.function(image=image, gpu="A10G", timeout=4 * 3600,
              volumes={"/hf": hf_cache, "/out": out_vol})
def train():
    import random

    import torch
    import torch.nn.functional as F
    from PIL import Image as PILImage
    from peft import LoraConfig, get_peft_model
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    dev = "cuda"
    with open("/manifest.json", encoding="utf-8") as f:
        splits = json.load(f)
    for split in splits.values():
        for item in split:
            # manifest paths come from Windows; basename manually on both slashes
            item["image"] = "/media/" + item["image"].replace("\\", "/").rsplit("/", 1)[-1]

    processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=MAX_PIXELS)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, device_map=dev)
    model.gradient_checkpointing_enable()

    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    hidden = model.config.text_config.hidden_size if hasattr(model.config, "text_config") \
        else model.config.hidden_size
    head = torch.nn.Linear(hidden, 1, dtype=torch.bfloat16).to(dev)

    prompt_text = ("Assess this social advertising creative for in-feed "
                   "engagement potential.")
    messages = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": prompt_text}]}]
    chat_text = processor.apply_chat_template(messages, tokenize=False,
                                              add_generation_prompt=True)

    def score(path, grad=True):
        img = PILImage.open(path).convert("RGB")
        inputs = processor(text=[chat_text], images=[img],
                           return_tensors="pt").to(dev)
        ctx = torch.enable_grad() if grad else torch.no_grad()
        with ctx:
            out = model(**inputs, output_hidden_states=True)
            hs = out.hidden_states[-1]
            idx = int(inputs["attention_mask"].sum(1).item()) - 1
            return head(hs[0, idx]).squeeze()

    train_items = splits["train"]
    tops = [i for i in train_items if i["stratum"] == "top"]
    bots = [i for i in train_items if i["stratum"] == "bottom"]
    all_pairs = [(t, b) for t in tops for b in bots]
    rng = random.Random(13)

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW([{"params": params, "lr": 1e-4},
                             {"params": head.parameters(), "lr": 1e-3}])
    lora_active = True
    step = 0
    for epoch in range(EPOCHS):
        pairs = rng.sample(all_pairs, min(PAIRS_PER_EPOCH, len(all_pairs)))
        running = 0.0
        for i, (t, b) in enumerate(pairs):
            try:
                loss = F.softplus(-(score(t["image"]) - score(b["image"]))) / GRAD_ACCUM
                loss.backward()
            except torch.cuda.OutOfMemoryError:
                # fall back to head-only training rather than dying unattended
                opt.zero_grad(set_to_none=True)
                torch.cuda.empty_cache()
                if lora_active:
                    for p in params:
                        p.requires_grad_(False)
                    lora_active = False
                    print("OOM -> continuing head-only")
                    continue
                raise
            running += float(loss) * GRAD_ACCUM
            if (i + 1) % GRAD_ACCUM == 0:
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                if step % 10 == 0:
                    print(f"epoch {epoch} step {step} loss {running / GRAD_ACCUM:.4f}")
                    running = 0.0

    def evaluate(items):
        scores = {it["id"]: float(score(it["image"], grad=False)) for it in items}
        top = [scores[i["id"]] for i in items if i["stratum"] == "top"]
        bot = [scores[i["id"]] for i in items if i["stratum"] == "bottom"]
        wins = sum(1 if t > b else 0.5 if t == b else 0 for t in top for b in bot)
        auc = wins / (len(top) * len(bot)) if top and bot else float("nan")
        return auc, scores

    train_auc, _ = evaluate(train_items)
    holdout_auc, holdout_scores = evaluate(splits["holdout"])
    metrics = {"model": MODEL_ID, "lora_active_at_end": lora_active,
               "train_auc": round(train_auc, 3),
               "holdout_auc": round(holdout_auc, 3),
               "n_train": len(train_items), "n_holdout": len(splits["holdout"]),
               "holdout_scores": holdout_scores}
    print(json.dumps({k: v for k, v in metrics.items() if k != "holdout_scores"}))

    model.save_pretrained("/out/adapter")
    torch.save(head.state_dict(), "/out/head.pt")
    with open("/out/metrics.json", "w") as f:
        json.dump(metrics, f)
    out_vol.commit()
    return metrics


@app.local_entrypoint()
def main():
    metrics = train.remote()
    path = os.path.join(FT_DIR, "data", "train_metrics.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=1)
    print(f"metrics -> {path}")
    print(json.dumps({k: v for k, v in metrics.items() if k != "holdout_scores"},
                     indent=1))
