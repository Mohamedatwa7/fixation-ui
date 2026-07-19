"""Run the judge-reliability harness using the Modal `anthropic` secret.

No local ANTHROPIC_API_KEY needed — variants and the report are built locally;
only the batch submit/poll/fetch runs remotely (CPU container, no GPU).

    python3 -m modal run eval/modal_runner.py                       # full run
    python3 -m modal run eval/modal_runner.py --images-dir my_kvs   # real KVs
    python3 -m modal run eval/modal_runner.py --fetch-run eval/runs/<ts>  # resume
"""

import json
import os
import sys
from datetime import datetime, timezone

import modal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = modal.App("f1x8-judge-eval")
image = modal.Image.debian_slim(python_version="3.12").pip_install("anthropic")


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic")], timeout=7200)
def submit_batch(requests: list) -> str:
    import anthropic
    return anthropic.Anthropic().messages.batches.create(requests=requests).id


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic")], timeout=7200)
def wait_and_fetch(batch_id: str) -> dict:
    import time
    import anthropic
    client = anthropic.Anthropic()
    while True:
        b = client.messages.batches.retrieve(batch_id)
        if b.processing_status == "ended":
            break
        print(f"batch {batch_id}: {b.processing_status} {b.request_counts}")
        time.sleep(30)
    out = {}
    for r in client.messages.batches.results(batch_id):
        if r.result.type == "succeeded":
            msg = r.result.message
            out[r.custom_id] = {
                "ok": True,
                "text": next((blk.text for blk in msg.content if blk.type == "text"), ""),
                "usage": {"input_tokens": msg.usage.input_tokens,
                          "output_tokens": msg.usage.output_tokens},
            }
        else:
            out[r.custom_id] = {"ok": False, "error": r.result.type}
    return out


@app.local_entrypoint()
def main(images_dir: str = "", fetch_run: str = "", repeats: int = 8, variant_repeats: int = 3):
    from judge_reliability import REPO_ROOT, build_run, synth_sample_ads, write_report

    if fetch_run:  # resume an interrupted run
        run_dir = fetch_run
        with open(os.path.join(run_dir, "batch_id.txt")) as f:
            batch_id = f.read().strip()
    else:
        images_dir = images_dir or os.path.join(REPO_ROOT, "eval", "assets")
        if not os.path.isdir(images_dir) or not os.listdir(images_dir):
            print(f"{images_dir} is empty — generating synthetic sample KVs")
            synth_sample_ads(images_dir)
        run_dir = os.path.join(REPO_ROOT, "eval", "runs",
                               datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
        os.makedirs(run_dir, exist_ok=True)
        _, requests = build_run(images_dir, run_dir, repeats, variant_repeats)
        print(f"{len(requests)} judge calls → submitting batch via Modal…")
        batch_id = submit_batch.remote(requests)
        with open(os.path.join(run_dir, "batch_id.txt"), "w") as f:
            f.write(batch_id)
        print(f"Batch {batch_id} submitted; polling until done (typically minutes)…")

    results = wait_and_fetch.remote(batch_id)
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("Report written:", write_report(run_dir))
