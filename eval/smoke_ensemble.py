"""Live smoke test of the ensembled assess_engagement (3 real API calls).

Extracts the judge + ensemble code from modal_app.py via AST (importing it
needs Modal auth) and runs it once on a sample KV. Requires ANTHROPIC_API_KEY.

Usage: python eval/smoke_ensemble.py [image_path]
"""
import ast
import base64
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_reliability as jr

FUNCS = ["_assess_engagement_once", "_kpi_score", "_majority", "_aggregate_judgments",
         "_neutral_engagement", "_parse_engagement_json", "assess_engagement"]
ASSIGNS = ["ENGAGEMENT_PROMPT", "ENGAGEMENT_SCHEMA", "_JUDGED_KPI_FIELDS", "JUDGE_SAMPLES"]

with open(jr.MODAL_APP_PATH, encoding="utf-8") as f:
    tree = ast.parse(f.read())
keep = [n for n in tree.body
        if (isinstance(n, ast.FunctionDef) and n.name in FUNCS)
        or (isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ASSIGNS for t in n.targets))]
ns = {"os": os, "json": json, "re": re}
exec(compile(ast.Module(body=keep, type_ignores=[]), "modal_app_extract", "exec"), ns)

img_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    jr.REPO_ROOT, "eval", "assets", "sample_offer_kv.jpg")
with open(img_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

t0 = time.time()
out = ns["assess_engagement"]([("image/jpeg", b64)])
dt = time.time() - t0
print(f"\nwall time: {dt:.1f}s")
print(json.dumps({k: (v.get("score") if isinstance(v, dict) and "score" in v else v)
                  for k, v in out.items()
                  if k in ns["_JUDGED_KPI_FIELDS"] + ["funnel_stage", "asset_intent"]},
                 indent=2))
assert out["funnel_stage"] in ("upper", "mid", "lower")
assert all(0 <= out[k]["score"] <= 10 for k in ns["_JUDGED_KPI_FIELDS"])
print("smoke test PASS")
