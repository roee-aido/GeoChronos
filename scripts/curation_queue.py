"""Merge the automatic curation queue (from a build) with the manual one (data/seed/curation_manual.csv).

Usage: python scripts/curation_queue.py --auto build/curation_queue_auto.csv --out build/runs/<run>/CURATION_QUEUE.csv
Prints counts by status and priority. Unresolved rows stay visible; nothing is dropped.
"""
import argparse
import collections
import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIELDS = ["id", "priority", "issue", "source", "action", "status", "rationale", "evidence", "origin"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", default=str(ROOT / "build" / "curation_queue_auto.csv"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    for path, origin in ((a.auto, "build (automatic)"), (ROOT / "data" / "seed" / "curation_manual.csv", "manual (night run)")):
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["origin"] = origin
                rows.append(r)
    rows.sort(key=lambda r: (r["priority"], r["status"] != "open", r["id"], r["issue"]))
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"{len(rows)} rows -> {out}")
    print("by status:", dict(collections.Counter(r["status"] for r in rows)))
    print("by priority:", dict(sorted(collections.Counter(r["priority"] for r in rows).items())))


if __name__ == "__main__":
    main()
