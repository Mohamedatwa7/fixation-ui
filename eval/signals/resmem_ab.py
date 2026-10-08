"""Candidate signal test: does image memorability (ResMem) predict engagement?

Scores the 132 labeled calibration creatives with ResMem (Needell & Bainbridge
2022 — trained on human memory-game data) and correlates with the realized
engagement percentiles, same metrics as the KPI A/Bs. A positive result makes
memorability a new grounded KPI; a null gets published to FINDINGS like the
others.

    D:\\F1X8\\.venv-train\\Scripts\\python.exe eval/signals/resmem_ab.py
"""

import json
import os
import sys

SIG_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(SIG_DIR))
OUT = os.path.join(SIG_DIR, "resmem_results.json")
sys.path.insert(0, os.path.join(REPO, "eval", "calibration"))

from aam_ab import spearman, auc, load_items  # noqa: E402


def main():
    import torch
    from PIL import Image
    from resmem import ResMem, transformer

    model = ResMem(pretrained=True).eval()
    if torch.cuda.is_available():
        model = model.cuda()
    items = load_items()
    xs, ys = [], []
    for it in items:
        img = Image.open(it["path"]).convert("RGB")
        x = transformer(img).unsqueeze(0)
        if torch.cuda.is_available():
            x = x.cuda()
        with torch.no_grad():
            xs.append(float(model(x).squeeze()))
        ys.append(it["percentile"])
    rho = spearman(xs, ys)
    med = sorted(ys)[len(ys) // 2]
    top = [x for x, y in zip(xs, ys) if y >= med]
    bot = [x for x, y in zip(xs, ys) if y < med]
    a = auc(top, bot)
    result = {"signal": "resmem_memorability", "n": len(xs),
              "spearman": round(rho, 3), "auc_median_split": round(a, 3),
              "mean": round(sum(xs) / len(xs), 3)}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
