"""Sanity-check _aggregate_judgments against real judge outputs from a run.

Extracts the aggregation functions from modal_app.py via AST (importing it
needs Modal auth), feeds them triples of real parsed judgments, and checks:
scores are per-KPI medians, categorical fields are majority votes, all
schema keys survive, and text fields come from a real sample.

Usage: python eval/test_aggregate.py --run eval/runs/<ts>
"""
import argparse
import ast
import itertools
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_reliability as jr

FUNCS = ["_kpi_score", "_majority", "_aggregate_judgments", "_neutral_engagement"]
ASSIGNS = ["_JUDGED_KPI_FIELDS", "JUDGE_SAMPLES"]


def load_funcs():
    with open(jr.MODAL_APP_PATH, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCS:
            keep.append(node)
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in ASSIGNS for t in node.targets):
            keep.append(node)
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "modal_app_extract", "exec"), ns)
    return ns


def main(run_dir):
    ns = load_funcs()
    aggregate = ns["_aggregate_judgments"]
    kpis = ns["_JUDGED_KPI_FIELDS"]

    with open(os.path.join(run_dir, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(run_dir, "results.json")) as f:
        results = json.load(f)

    by_image = {}
    for cid, meta in manifest.items():
        if meta["variant"] != "original":
            continue
        j = jr.parse_engagement(results.get(cid, {}).get("text"))
        if j is not None:
            by_image.setdefault(meta["image"], []).append(j)

    checks = failures = 0
    for img, runs in sorted(by_image.items()):
        for triple in itertools.combinations(runs, 3):
            agg = aggregate(list(triple))
            for k in kpis:
                checks += 1
                want = statistics.median(ns["_kpi_score"](j, k) for j in triple)
                if agg[k]["score"] != want:
                    failures += 1
                    print(f"FAIL {img}/{k}: score {agg[k]['score']} != median {want}")
            for field in ("funnel_stage", "product_tier", "asset_intent",
                          "primary_engagement_driver", "primary_engagement_risk"):
                checks += 1
                if field.startswith("primary"):
                    ok = agg[field] in [j.get(field) for j in triple]
                else:
                    # Independent oracle: the winner must hold a maximal vote
                    # count (ties may legitimately break either way).
                    counts = Counter(j.get(field) for j in triple
                                     if j.get(field) is not None)
                    ok = (agg[field] is None if not counts
                          else counts[agg[field]] == max(counts.values()))
                if not ok:
                    failures += 1
                    print(f"FAIL {img}/{field}: {agg[field]!r}")
            checks += 1
            missing = set(triple[0]) - set(agg)
            if missing:
                failures += 1
                print(f"FAIL {img}: missing keys {missing}")
    # degenerate inputs
    neutral = ns["_neutral_engagement"]()
    assert aggregate([neutral]) == neutral
    assert aggregate([neutral, neutral, neutral])["funnel_stage"] == "mid"
    print(f"{checks} checks over all C(8,3) triples x 2 images: {failures} failures")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    main(p.parse_args().run)
