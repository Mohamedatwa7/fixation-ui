"""Overnight chain: CreativeRanking pretrain epoch 2 -> Samsung re-fine-tune.

Epoch 1 ended with the holdout curve still rising (0.697@20k -> 0.709@38.5k),
so a second pass over the same 38.5k pairs in a new order is the cheapest
upside available. Afterwards, re-run the Samsung fine-tune from the improved
adapter and compare against the 0.921 incumbent (frozen 82-creative holdout).
Promotion stays manual — results land in FINDINGS-worthy JSON only.
"""

import json
import os
import random
import sys

FT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FT_DIR)
import pretrain_ranker_cr as M

# Same pairs, epoch-2 order; fresh progress counter; weights auto-resume
# from the epoch-1 adapter (cmd_train loads it whenever it exists).
with open(M.PAIRS_PATH, encoding="utf-8") as f:
    pairs = json.load(f)
train = [p for p in pairs if p["split"] == "train"]
hold = [p for p in pairs if p["split"] == "holdout"]
random.Random(49).shuffle(train)
p2 = os.path.join(M.OUT_DIR, "pairs_epoch2.json")
with open(p2, "w", encoding="utf-8") as f:
    json.dump(train + hold, f)
M.PAIRS_PATH = p2

state_path = os.path.join(M.OUT_DIR, "train_state.json")
if os.path.exists(state_path):
    with open(state_path, encoding="utf-8") as f:
        st = json.load(f)
    if st.get("pairs_done", 0) >= len(train) and not st.get("epoch2"):
        # starting epoch 2 fresh (keep epoch-1 record aside)
        os.replace(state_path, os.path.join(M.OUT_DIR, "train_state_epoch1.json"))
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"pairs_done": 0, "model_id": M.MODEL_ID, "epoch2": True}, f)

print("=== EPOCH 2: pretrain continuation ===", flush=True)
M.cmd_train()

# free the pretrain model before the fine-tune loads its own copy — the
# 5090 also hosts the serving sidecar (~9GB resident)
import gc
import torch
gc.collect()
torch.cuda.empty_cache()

print("=== Samsung re-fine-tune from epoch-2 adapter ===", flush=True)
import finetune_samsung as ft
ft.VARIANTS["pre2_lr5e6"] = {"pretrained": True, "lr": 5e-6}
best = ft.run_variant("pre2_lr5e6", ft.VARIANTS["pre2_lr5e6"])
print(f"=== CHAIN DONE: pre2_lr5e6 holdout AUC {best:.3f} "
      f"(incumbent pre_lr5e6 = 0.921) ===")
