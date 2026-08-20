"""Compare two analysis result JSONs (e.g. original vs adapted KV).

Usage: python scripts/compare_scores.py <original.json> <adapted.json>
"""
import json
import sys


def main():
    a = json.load(open(sys.argv[1], encoding="utf-8"))
    b = json.load(open(sys.argv[2], encoding="utf-8"))

    print(f"{'':24s} {'original':>10s} {'adapted':>10s}")
    for field in ("score", "engagement_potential", "kpis_overall", "organic_engagement"):
        print(f"{field:24s} {str(a.get(field)):>10s} {str(b.get(field)):>10s}")
    print()
    for k in sorted(set(a.get("kpis", {})) | set(b.get("kpis", {}))):
        sa = a.get("kpis", {}).get(k, {}).get("score", "-")
        sb = b.get("kpis", {}).get(k, {}).get("score", "-")
        print(f"kpi:{k:20s} {str(sa):>10s} {str(sb):>10s}")

    for label, r in (("ORIGINAL", a), ("ADAPTED", b)):
        v = r.get("verdict", {})
        print(f"\n--- {label} ---")
        print("summary:", v.get("summary", ""))
        for risk in v.get("risks", [])[:3]:
            print(f"  risk {risk.get('rank')}: {risk.get('issue', '')}")


if __name__ == "__main__":
    main()
