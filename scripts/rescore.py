"""Score an image via the deployed F1X8 backend and save the result JSON.

Usage: python scripts/rescore.py <image> <out.json> [format_type]
Reads F1X8_API_URL from eval/calibration/.env (or the environment).
"""
import json
import os
import sys

import requests


def main():
    image, out = sys.argv[1], sys.argv[2]
    format_type = sys.argv[3] if len(sys.argv) > 3 else "kv"

    env_path = os.path.join("eval", "calibration", ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)

    base = os.environ["F1X8_API_URL"].rstrip("/")
    if "vercel.app" in base:
        url = f"{base}/api/analyze?endpoint=/api/analyze/image"
    else:
        url = f"{base}/api/analyze/image"

    with open(image, "rb") as f:
        content = f.read()
    r = requests.post(url, files={"file": (os.path.basename(image), content)},
                      data={"format_type": format_type}, timeout=580)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise SystemExit(f"backend error: {body['error'][:300]}")
    body.pop("heatmap", None)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
    print("saved", out)
    print("score:", body.get("score"),
          "| engagement_potential:", body.get("engagement_potential"),
          "| kpis_overall:", body.get("kpis_overall"))


if __name__ == "__main__":
    main()
