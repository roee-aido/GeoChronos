"""Fetch a raw Wikidata snapshot for the GeoChronos seed targets.

Reads data/seed/wikidata_targets.json, runs every scripts/sparql/*.rq query
against the Wikidata Query Service and writes the untouched responses to
data/raw/wikidata_<YYYY-MM-DD>.json together with the queries and retrieval
time, so every imported value can be traced back to what Wikidata said.

Stdlib only.  Usage:  python scripts/fetch_wikidata.py
"""
import datetime as dt
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "GeoChronosPOC/0.1 (research prototype)"


def load_targets():
    targets = json.loads((ROOT / "data/seed/wikidata_targets.json").read_text(encoding="utf-8"))
    qids = {}
    for group in ("items", "events", "persons", "places"):
        qids.update({k: v for k, v in targets.get(group, {}).items() if not k.startswith("_")})
    return qids


def run_query(sparql):
    body = urllib.parse.urlencode({"query": sparql}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    qids = load_targets()
    values = " ".join(f"wd:{q}" for q in sorted(set(qids.values())))
    now = dt.datetime.now(dt.timezone.utc)
    snapshot = {
        "endpoint": ENDPOINT,
        "retrieved_at": now.isoformat(timespec="seconds"),
        "license": "CC0 1.0 (Wikidata structured data)",
        "targets": qids,
        "queries": {},
    }
    for rq in sorted((ROOT / "scripts/sparql").glob("*.rq")):
        sparql = rq.read_text(encoding="utf-8").replace("{{VALUES}}", values)
        print(f"running {rq.name} ...")
        snapshot["queries"][rq.stem] = {"sparql": sparql, "results": run_query(sparql)}
        time.sleep(2)  # be polite to WDQS
    out = ROOT / f"data/raw/wikidata_{now.date().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
