"""Local dry-run: verify the harness builds a full batch (no API call)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_reliability as jr

assets = os.path.join(jr.REPO_ROOT, "eval", "assets")
if not os.path.isdir(assets) or not os.listdir(assets):
    jr.synth_sample_ads(assets)
run_dir = os.path.join(jr.REPO_ROOT, "eval", "runs", "dryrun")
os.makedirs(run_dir, exist_ok=True)
manifest, requests = jr.build_run(assets, run_dir)
prompt = jr.load_engagement_prompt()
schema = jr.load_engagement_schema()
print("images:", sorted({m["image"] for m in manifest.values()}))
print("requests:", len(requests))
print("prompt chars:", len(prompt), "| schema present:", schema is not None)
print("variants:", sorted({m["variant"] for m in manifest.values()}))
