"""Serve the fine-tuned engagement ranker as a standalone Modal endpoint.

Additive service: the main fixation-api is untouched. The ranker score is a
relative organic-engagement rank signal (higher = more likely to out-engage
peer creatives from the same feed), NOT a calibrated 0-10 quality score.

    python -m modal deploy eval/finetune/serve_ranker_modal.py
    POST https://<workspace>--rank.modal.run  with JSON {"image_b64": "<base64 jpeg/png>"}

Returns {"rank_score": float, "note": ...}. Scores are comparable between
creatives scored by the same adapter version; sigmoid-squashed to 0-10 using
the holdout score distribution for readability.
"""

import json
import os

import modal

# v2 (2026-10-07): Qwen3-VL-4B + CreativeRanking pretrain + Samsung
# fine-tune — holdout AUC 0.921 vs the v1 (Qwen2.5-VL-3B) 0.851. Adapter at
# /adapter/pre_lr5e6; v1 artifacts stay on the volume for rollback.
MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"
MAX_PIXELS = 512 * 28 * 28
ADAPTER_DIR = "/adapter/pre_lr5e6"
# Dual-model serving: "model" field selects. organic = pre_lr5e6 (0.921 on
# organic brand IG); owned = Sprinklr-trained (/adapter/sprinklr, 0.854 on
# Samsung-owned multi-platform; 6+ scores -> 97% top-quartile).
VARIANT_DIRS = {"organic": "/adapter/pre_lr5e6", "owned": "/adapter/sprinklr"}

app = modal.App("fixation-ranker-api")
hf_cache = modal.Volume.from_name("fixation-ranker-hf", create_if_missing=True)
adapter_vol = modal.Volume.from_name("fixation-ranker", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    # Pins mirror the local .venv-train that trained/validated this adapter.
    .pip_install("torch", "torchvision", "transformers==5.18.0", "peft==0.21.2",
                 "accelerate==1.15.0", "pillow", "fastapi[standard]")
    .env({"HF_HOME": "/hf"})
)


@app.cls(image=image, gpu="A10G", timeout=600, scaledown_window=120,
         volumes={"/hf": hf_cache, "/adapter": adapter_vol})
class Ranker:
    @modal.enter()
    def load(self):
        import torch
        from peft import PeftModel
        from transformers import AutoProcessor, AutoModelForImageTextToText

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=MAX_PIXELS)
        base = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
        self.model = PeftModel.from_pretrained(
            base, f"{VARIANT_DIRS['organic']}/adapter", adapter_name="organic")
        if os.path.isdir(f"{VARIANT_DIRS['owned']}/adapter"):
            self.model.load_adapter(f"{VARIANT_DIRS['owned']}/adapter",
                                    adapter_name="owned")
        self.model = self.model.eval()
        hidden = base.config.text_config.hidden_size if hasattr(base.config, "text_config") \
            else base.config.hidden_size
        self.heads, self.calib = {}, {}
        for name, d in VARIANT_DIRS.items():
            if not os.path.exists(f"{d}/head.pt"):
                continue
            h = torch.nn.Linear(hidden, 1, dtype=torch.bfloat16).to("cuda")
            h.load_state_dict(torch.load(f"{d}/head.pt", map_location="cuda"))
            h.eval()
            self.heads[name] = h
            with open(f"{d}/calibration.json") as f:
                scores = sorted(json.load(f).get("holdout_scores", {}).values())
            if scores:
                mid = scores[len(scores) // 2]
                spread = (scores[int(0.9 * len(scores))]
                          - scores[int(0.1 * len(scores))]) or 1.0
                self.calib[name] = (mid, 2.0 / spread)
            else:
                self.calib[name] = (0.0, 1.0)

        messages = [{"role": "user", "content": [
            {"type": "image"},
            # Must byte-match the training prompt (pretrain_ranker_cr /
            # finetune_samsung), or scores shift subtly.
            {"type": "text", "text": "Assess this e-commerce advertising creative "
                                     "for in-feed engagement potential."}]}]
        self.chat_text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)

    @modal.fastapi_endpoint(method="POST", label="rank")
    def rank(self, item: dict):
        import base64
        import io

        from PIL import Image as PILImage

        variant = item.get("model") or "organic"
        if variant not in self.heads:
            variant = "organic"
        img = PILImage.open(io.BytesIO(base64.b64decode(item["image_b64"]))).convert("RGB")
        self.model.set_adapter(variant)
        inputs = self.processor(text=[self.chat_text], images=[img],
                                return_tensors="pt").to("cuda")
        with self.torch.no_grad():
            out = self.model(**inputs, output_hidden_states=True)
            hs = out.hidden_states[-1]
            idx = int(inputs["attention_mask"].sum(1).item()) - 1
            raw = float(self.heads[variant](hs[0, idx]).squeeze())
        mid, scale = self.calib[variant]
        squashed = 10.0 / (1.0 + pow(2.718281828, -(raw - mid) * scale))
        return {
            "rank_score": round(squashed, 2),
            "raw": round(raw, 4),
            "model": variant,
            "note": ("Relative organic-engagement rank signal (fine-tuned "
                     "pairwise ranker); compare between creatives, not an "
                     "absolute quality score."),
        }
