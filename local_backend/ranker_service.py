"""Local ranker sidecar — serves the fine-tuned organic-engagement ranker.

Mirrors the Modal fixation-ranker `rank` endpoint contract exactly
(POST {image_b64} -> {rank_score, raw, note}) so modal_app._rank_score works
unchanged with RANKER_URL pointed here. Runs in .venv-train (Qwen3-VL needs
a newer transformers than the serving venv) on port 8012:

    .\\ranker_run.ps1     (or: ..\\.venv-train\\Scripts\\python.exe -m uvicorn
                           ranker_service:app --host 127.0.0.1 --port 8012)

Model: Qwen3-VL-4B + CreativeRanking-pretrained, Samsung-fine-tuned LoRA
(eval/finetune/out_samsung/pre_lr5e6; holdout AUC 0.921 vs 0.851 baseline).
Raw scores are squashed to 0-10 with the same median/P10-P90 sigmoid the
Modal server used, referenced to the holdout score distribution.
"""

import base64
import io
import json
import math
import os
import threading
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ADAPTER_DIR = REPO / "eval" / "finetune" / "out_samsung" / "pre_lr5e6"
MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"
MAX_PIXELS = 512 * 28 * 28

os.environ.setdefault("HF_HOME", str(ROOT / "hf-cache"))

app = FastAPI()
_STATE = {}
_LOCK = threading.RLock()  # reentrant: /rank holds it while _load() re-acquires


def _load():
    if _STATE:
        return _STATE
    with _LOCK:
        if _STATE:
            return _STATE
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        from peft import PeftModel
        print("[ranker] loading model...")
        processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=MAX_PIXELS)
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
        model = PeftModel.from_pretrained(model, str(ADAPTER_DIR / "adapter")).eval()
        hidden = getattr(model.config, "text_config", model.config).hidden_size
        head = torch.nn.Linear(hidden, 1, dtype=torch.bfloat16).to("cuda")
        head.load_state_dict(torch.load(ADAPTER_DIR / "head.pt",
                                        weights_only=True))
        head.eval()
        with open(ADAPTER_DIR / "calibration.json", encoding="utf-8") as f:
            scores = sorted(json.load(f)["holdout_scores"].values())
        mid = scores[len(scores) // 2]
        spread = (scores[int(0.9 * len(scores))]
                  - scores[int(0.1 * len(scores))]) or 1.0
        msgs = [{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": "Assess this e-commerce advertising "
                                     "creative for in-feed engagement potential."}]}]
        chat = processor.apply_chat_template(msgs, tokenize=False,
                                             add_generation_prompt=True)
        _STATE.update(torch=torch, processor=processor, model=model, head=head,
                      mid=mid, scale=2.0 / spread, chat=chat)
        print(f"[ranker] ready (mid={mid:.3f}, scale={_STATE['scale']:.3f})")
        return _STATE


def _score_raw(img):
    st = _load()
    torch = st["torch"]
    inputs = st["processor"](text=[st["chat"]], images=[img],
                             return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = st["model"](**inputs, output_hidden_states=True)
        hs = out.hidden_states[-1]
        idx = int(inputs["attention_mask"].sum(1).item()) - 1
        return float(st["head"](hs[0, idx]).squeeze())


@app.post("/rank")
def rank(item: dict):
    from PIL import Image as PILImage
    try:
        img = PILImage.open(io.BytesIO(
            base64.b64decode(item["image_b64"]))).convert("RGB")
        with _LOCK:
            raw = _score_raw(img)
        st = _STATE
        squashed = 10.0 / (1.0 + math.exp(-(raw - st["mid"]) * st["scale"]))
        return {
            "rank_score": round(squashed, 2),
            "raw": round(raw, 4),
            "note": ("Relative organic-engagement rank signal (CreativeRanking-"
                     "pretrained, Samsung-fine-tuned ranker, holdout AUC 0.921); "
                     "compare between creatives, not an absolute quality score."),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok", "loaded": bool(_STATE),
            "adapter": str(ADAPTER_DIR), "model_id": MODEL_ID,
            "holdout_auc": 0.921}
