"""GeoChronos ingestion: raw snapshot -> staging (the build does mapping -> claims/evidence).

Layout (raw is write-once; staging is re-generable):
  data/raw/<source>/<snapshot_id>/            untouched responses + MANIFEST.json
  data/raw/wikidata_2026-09-30.json           legacy single-file snapshot (kept as-is; manifest beside it)
  data/staging/<source>/<snapshot_id>.jsonl   normalised records consumed by scripts/build_db.py
  data/cache/http/<sha256>.json               HTTP cache (not provenance; may be deleted)

Commands
  python scripts/ingest.py wikidata [--dry-run] [--resume SNAPSHOT_ID] [--batch 50]
  python scripts/ingest.py pleiades [--dry-run] [--resume SNAPSHOT_ID]
  python scripts/ingest.py stage                 (re-stage every complete snapshot)
  python scripts/ingest.py register-legacy       (manifest + staging for the 2026-09-30 single-file snapshot)
  python scripts/ingest.py status

Behaviour: batched requests, timeout, at most 4 retries with exponential backoff
(honours Retry-After), resume of incomplete snapshots, dry-run, polite delays.
Stdlib only.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
STAGING = ROOT / "data" / "staging"
CACHE = ROOT / "data" / "cache" / "http"
SEED = ROOT / "data" / "seed"
USER_AGENT = "GeoChronosPOC/0.2 (research prototype; low-volume)"
WDQS = "https://query.wikidata.org/sparql"
PLEIADES = "https://pleiades.stoa.org/places/{pid}/json"
MAX_RETRIES = 4
TIMEOUT = 120

TERMS = {
    "wikidata": {"license": "CC0 1.0 (structured data)", "terms_url": "https://www.wikidata.org/wiki/Wikidata:Licensing",
                 "terms_checked_at": "2026-10-01", "terms_status": "verified (official licensing page read 2026-10-01)"},
    "pleiades": {"license": "CC BY 3.0", "terms_url": "https://pleiades.stoa.org/downloads ; https://pleiades.stoa.org/credits",
                 "terms_checked_at": "2026-10-01",
                 "terms_status": "verified (downloads + credits pages: 'Creative Commons Attribution 3.0 License (cc-by)'); "
                                 "attribution: Ancient World Mapping Center and Institute for the Study of the Ancient World"},
}


def now():
    return dt.datetime.now().astimezone()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- HTTP ----

def http(method, url, data=None, headers=None, use_cache=True, log=None):
    """GET/POST with cache, timeout, bounded retries and backoff. Returns (bytes, meta)."""
    headers = dict(headers or {}, **{"User-Agent": USER_AGENT})
    key = sha256_bytes(json.dumps([method, url, data], sort_keys=True).encode())
    cpath = CACHE / f"{key}.json"
    if use_cache and cpath.exists():
        c = json.loads(cpath.read_text(encoding="utf-8"))
        return c["body"].encode("utf-8"), {"from_cache": True, "fetched_at": c["fetched_at"], "status": c["status"]}
    body = None if data is None else urllib.parse.urlencode(data).encode()
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
                meta = {"from_cache": False, "fetched_at": now().isoformat(timespec="seconds"), "status": r.status}
                CACHE.mkdir(parents=True, exist_ok=True)
                cpath.write_text(json.dumps({"url": url, "fetched_at": meta["fetched_at"], "status": r.status,
                                             "body": raw.decode("utf-8")}), encoding="utf-8")
                return raw, meta
        except urllib.error.HTTPError as e:
            retryable = e.code in (429, 500, 502, 503, 504)
            wait = int(e.headers.get("Retry-After", 0) or 0) or 2 ** (attempt + 1)
            if log is not None:
                log.append({"url": url, "attempt": attempt, "error": f"HTTP {e.code}", "retry": retryable and attempt < MAX_RETRIES})
            if not retryable or attempt == MAX_RETRIES:
                raise
            time.sleep(min(wait, 60))
        except (urllib.error.URLError, TimeoutError) as e:
            if log is not None:
                log.append({"url": url, "attempt": attempt, "error": str(e), "retry": attempt < MAX_RETRIES})
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 ** (attempt + 1))


# ------------------------------------------------------------- targets ----

def wikidata_targets():
    qids = {}
    for f in ("wikidata_targets.json", "wikidata_targets_expansion.json"):
        p = SEED / f
        if not p.exists():
            continue
        t = json.loads(p.read_text(encoding="utf-8"))
        for group, mapping in t.items():
            if group.startswith("_") or not isinstance(mapping, dict):
                continue
            qids.update({k: v for k, v in mapping.items() if not k.startswith("_")})
    return qids


def new_snapshot_dir(source, resume):
    if resume:
        d = RAW / source / resume
        if not d.exists():
            sys.exit(f"no snapshot {resume} to resume")
        m = d / "MANIFEST.json"
        if m.exists() and json.loads(m.read_text(encoding="utf-8")).get("status") == "complete":
            sys.exit(f"snapshot {resume} is complete and immutable; start a new one instead")
        return d
    sid = now().strftime("%Y-%m-%dT%H%M%S%z")
    d = RAW / source / sid
    d.mkdir(parents=True, exist_ok=False)
    return d


def write_manifest(d, source, extra):
    files = {f.name: {"sha256": sha256_bytes(f.read_bytes()), "bytes": f.stat().st_size}
             for f in sorted(d.iterdir()) if f.name != "MANIFEST.json"}
    m = {"snapshot_id": d.name, "source": source, "status": "complete", "completed_at": now().isoformat(timespec="seconds"),
         "files": files, **TERMS[source], **extra}
    (d / "MANIFEST.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return m


# ------------------------------------------------------------ Wikidata ----

def cmd_wikidata(args):
    qids = wikidata_targets()
    unique = sorted(set(qids.values()), key=lambda q: int(q[1:]))
    batches = [unique[i:i + args.batch] for i in range(0, len(unique), args.batch)]
    queries = sorted((ROOT / "scripts" / "sparql").glob("*.rq"))
    print(f"{len(unique)} QIDs, {len(batches)} batch(es) x {len(queries)} queries = {len(batches) * len(queries)} requests")
    if args.dry_run:
        for q in queries:
            for i, _ in enumerate(batches):
                print(f"  would POST {WDQS}  {q.stem}  batch {i}")
        return
    d = new_snapshot_dir("wikidata", args.resume)
    started = now().isoformat(timespec="seconds")
    errors = []
    for q in queries:
        template = q.read_text(encoding="utf-8")
        for i, batch in enumerate(batches):
            out = d / f"{q.stem}__b{i:02d}.json"
            if out.exists():                                     # resume
                continue
            sparql = template.replace("{{VALUES}}", " ".join(f"wd:{x}" for x in batch))
            raw, meta = http("POST", WDQS, {"query": sparql}, {"Accept": "application/sparql-results+json"},
                             use_cache=not args.no_cache, log=errors)
            json.loads(raw)                                       # must parse
            out.write_bytes(raw)
            (d / f"{q.stem}__b{i:02d}.request.json").write_text(json.dumps(
                {"endpoint": WDQS, "query_file": f"scripts/sparql/{q.name}", "sparql_sha256": sha256_bytes(sparql.encode()),
                 "qids": batch, **meta}, indent=1), encoding="utf-8")
            print(f"  {out.name} {'(cache)' if meta['from_cache'] else ''}")
            if not meta["from_cache"]:
                time.sleep(2)
    m = write_manifest(d, "wikidata", {"endpoint": WDQS, "started_at": started, "targets": qids,
                                       "batch_size": args.batch, "retry_log": errors})
    print(f"snapshot complete: {d.relative_to(ROOT)} ({len(m['files'])} files)")
    stage_wikidata(d)


def stage_wikidata(d):
    """Raw WDQS JSON -> staging JSONL: one record per binding, values flattened, snapshot metadata attached."""
    m = json.loads((d / "MANIFEST.json").read_text(encoding="utf-8"))
    out = STAGING / "wikidata" / f"{d.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_snapshot": {"snapshot_id": d.name, "retrieved_at": m.get("started_at") or m["completed_at"],
                                           "targets": m["targets"], "raw_dir": str(d.relative_to(ROOT))}}) + "\n")
        for f in sorted(d.glob("*__b*.json")):
            if f.name.endswith(".request.json"):
                continue
            query = f.name.split("__")[0]
            for b in json.loads(f.read_text(encoding="utf-8"))["results"]["bindings"]:
                fh.write(json.dumps({"query": query, "b": {k: v["value"] for k, v in b.items()}}, ensure_ascii=False) + "\n")
                n += 1
    print(f"staged {n} records -> {out.relative_to(ROOT)}")


def cmd_register_legacy(args):
    legacy = RAW / "wikidata_2026-09-30.json"
    snap = json.loads(legacy.read_text(encoding="utf-8"))
    sid = "2026-09-30T-legacy"
    mpath = RAW / "wikidata_2026-09-30.MANIFEST.json"
    if not mpath.exists():
        m = {"snapshot_id": sid, "source": "wikidata", "status": "complete", "format": "legacy-single-file",
             "file": legacy.name, "sha256": sha256_bytes(legacy.read_bytes()), "endpoint": snap["endpoint"],
             "retrieved_at": snap["retrieved_at"], "targets": snap["targets"],
             "queries": {k: {"sparql_sha256": sha256_bytes(v["sparql"].encode())} for k, v in snap["queries"].items()},
             "note": "Created 2026-10-01 night run; the snapshot file itself is unchanged. retrieved_at is UTC as recorded at fetch time.",
             **TERMS["wikidata"]}
        mpath.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    out = STAGING / "wikidata" / f"{sid}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_snapshot": {"snapshot_id": sid, "retrieved_at": snap["retrieved_at"], "targets": snap["targets"],
                                           "raw_dir": str(legacy.relative_to(ROOT))}}) + "\n")
        for q, v in snap["queries"].items():
            for b in v["results"]["results"]["bindings"]:
                fh.write(json.dumps({"query": q, "b": {k: x["value"] for k, x in b.items()}}, ensure_ascii=False) + "\n")
                n += 1
    print(f"legacy snapshot registered; staged {n} records -> {out.relative_to(ROOT)}")


# ------------------------------------------------------------ Pleiades ----

def pleiades_ids_from_staging():
    """Pleiades IDs come only from verified external IDs (Wikidata P1584) in staged Wikidata snapshots."""
    ids = {}
    for f in sorted((STAGING / "wikidata").glob("*.jsonl")):
        targets = None
        for line in f.open(encoding="utf-8"):
            r = json.loads(line)
            if "_snapshot" in r:
                targets = {v: k for k, v in r["_snapshot"]["targets"].items()}
                continue
            if r["query"] == "extids" and r["b"]["prop"] == "P1584":
                q = r["b"]["item"].rsplit("/", 1)[1]
                ids.setdefault(r["b"]["value"], set()).add(targets.get(q, q))
    return ids


def cmd_pleiades(args):
    ids = pleiades_ids_from_staging()
    print(f"{len(ids)} Pleiades IDs (from Wikidata P1584)")
    if args.dry_run:
        for pid in sorted(ids):
            print("  would GET", PLEIADES.format(pid=pid), "->", sorted(ids[pid]))
        return
    d = new_snapshot_dir("pleiades", args.resume)
    started = now().isoformat(timespec="seconds")
    errors = []
    for pid in sorted(ids):
        out = d / f"{pid}.json"
        if out.exists():
            continue
        try:
            raw, meta = http("GET", PLEIADES.format(pid=pid), headers={"Accept": "application/json"},
                             use_cache=not args.no_cache, log=errors)
            json.loads(raw)
            out.write_bytes(raw)
            print(f"  {pid} {'(cache)' if meta['from_cache'] else ''}")
            if not meta["from_cache"]:
                time.sleep(1.5)
        except Exception as e:                                   # keep going; record the failure
            errors.append({"pid": pid, "error": repr(e)})
            print(f"  {pid} FAILED {e!r}")
    m = write_manifest(d, "pleiades", {"endpoint": PLEIADES, "started_at": started,
                                       "ids": {k: sorted(v) for k, v in ids.items()}, "errors": errors})
    print(f"snapshot complete: {d.relative_to(ROOT)} ({len(m['files'])} files, {len(errors)} errors)")
    stage_pleiades(d)


def stage_pleiades(d):
    m = json.loads((d / "MANIFEST.json").read_text(encoding="utf-8"))
    out = STAGING / "pleiades" / f"{d.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_snapshot": {"snapshot_id": d.name, "retrieved_at": m["started_at"], "ids": m["ids"],
                                           "raw_dir": str(d.relative_to(ROOT))}}) + "\n")
        for f in sorted(d.glob("*.json")):
            if f.name == "MANIFEST.json":
                continue
            p = json.loads(f.read_text(encoding="utf-8"))
            names = [{"attested": n.get("attested") or None, "romanized": n.get("romanized"), "language": n.get("language"),
                      "start": n.get("start"), "end": n.get("end"), "nameType": n.get("nameType"),
                      "associationCertainty": n.get("associationCertainty"),
                      "periods": sorted({a.get("timePeriod") for a in n.get("attestations", []) if a.get("timePeriod")})}
                     for n in p.get("names", [])]
            fh.write(json.dumps({"pid": f.stem, "title": p.get("title"), "uri": p.get("uri"),
                                 "reprPoint": p.get("reprPoint"), "placeTypes": p.get("placeTypes"),
                                 "review_state": p.get("review_state"), "names": names}, ensure_ascii=False) + "\n")
    print(f"staged -> {out.relative_to(ROOT)}")


# ------------------------------------------------------------- generic ----

def cmd_stage(args):
    for src, fn in (("wikidata", stage_wikidata), ("pleiades", stage_pleiades)):
        for d in sorted((RAW / src).glob("*")) if (RAW / src).exists() else []:
            m = d / "MANIFEST.json"
            if m.exists() and json.loads(m.read_text(encoding="utf-8")).get("status") == "complete":
                fn(d)
    if (RAW / "wikidata_2026-09-30.json").exists():
        cmd_register_legacy(args)


def cmd_status(args):
    for src in ("wikidata", "pleiades"):
        for d in sorted((RAW / src).glob("*")) if (RAW / src).exists() else []:
            m = d / "MANIFEST.json"
            st = json.loads(m.read_text(encoding="utf-8")).get("status") if m.exists() else "INCOMPLETE (resumable)"
            print(f"{src:9s} {d.name}  {st}")
    if (RAW / "wikidata_2026-09-30.MANIFEST.json").exists():
        print("wikidata  2026-09-30T-legacy  complete (legacy single file)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("wikidata", "pleiades"):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--resume")
        p.add_argument("--no-cache", action="store_true")
        p.add_argument("--batch", type=int, default=50)
    sub.add_parser("stage")
    sub.add_parser("register-legacy")
    sub.add_parser("status")
    args = ap.parse_args()
    {"wikidata": cmd_wikidata, "pleiades": cmd_pleiades, "stage": cmd_stage,
     "register-legacy": cmd_register_legacy, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()
