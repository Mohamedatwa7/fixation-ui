"""Print the KPI scores and risk levers from an analysis result JSON.

Usage: python scripts/inspect_result.py <result.json>
"""
import json
import sys


def main():
    r = json.load(open(sys.argv[1], encoding="utf-8"))
    print("kpis:", {k: v["score"] for k, v in r.get("kpis", {}).items()})
    print("funnel:", r.get("funnel_stage"), "| organic:", r.get("organic_engagement"))
    for x in r.get("verdict", {}).get("risks", []):
        print(f"\nrisk {x.get('rank')} [{x.get('confidence')}] lever={x.get('score_lever', 'MISSING')}")
        print("  issue:", x.get("issue", "")[:160])
        print("  fix:", x.get("suggested_fix", "")[:160])


if __name__ == "__main__":
    main()
