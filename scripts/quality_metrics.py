"""Data-quality metrics for one or more GeoChronos databases (markdown table to stdout).

Usage: python scripts/quality_metrics.py LABEL=PATH [LABEL=PATH ...]
Works on older builds too (metrics that need newer columns print 'n/a').
"""
import sqlite3
import sys

ACTIVE = "('construction','creation','use','occupation','existence','event','deposition','destruction','reign','life','first_record')"
USABLE = "c.rank <> 'deprecated' AND c.status <> 'rejected'"

METRICS = [
    ("Items", "SELECT COUNT(*) FROM entity WHERE kind='item'"),
    ("Entities", "SELECT COUNT(*) FROM entity"),
    ("Claims", "SELECT COUNT(*) FROM claim"),
    ("Evidence rows", "SELECT COUNT(*) FROM claim_evidence"),
    ("Relations", "SELECT COUNT(*) FROM relation"),
    ("Temporal extents", "SELECT COUNT(*) FROM temporal_extent"),
    ("Locations", "SELECT COUNT(*) FROM location"),
    ("Names", "SELECT COUNT(*) FROM entity_name"),
    ("Hebrew names (rows)", "SELECT COUNT(*) FROM entity_name WHERE lang='he'"),
    ("Items with a Hebrew name", "SELECT COUNT(DISTINCT n.entity_id) FROM entity_name n JOIN entity e USING(entity_id) WHERE e.kind='item' AND n.lang='he'"),
    ("External IDs", "SELECT COUNT(*) FROM external_id"),
    ("Dispute groups", "SELECT COUNT(DISTINCT dispute_group) FROM claim WHERE dispute_group IS NOT NULL"),
    ("Claims disputed / alternative", "SELECT COUNT(*) FROM claim WHERE status IN ('disputed','alternative')"),
    ("Claims rejected (kept for audit)", "SELECT COUNT(*) FROM claim WHERE status='rejected'"),
    ("Claims deprecated (superseded)", "SELECT COUNT(*) FROM claim WHERE rank='deprecated'"),
    ("Claims needs_verification", "SELECT COUNT(*) FROM claim WHERE status='needs_verification'"),
    ("Claims confidence 'high'", "SELECT COUNT(*) FROM claim WHERE confidence='high'"),
    ("Imported claims with automatic 'high'", "SELECT COUNT(*) FROM claim WHERE recorded_by LIKE 'import:%' AND confidence='high'"),
    ("Items with dated activity (usable)", f"""SELECT COUNT(DISTINCT t.entity_id) FROM temporal_extent t JOIN claim c ON c.claim_id=t.claim_id
         JOIN entity e ON e.entity_id=t.entity_id WHERE e.kind='item' AND t.role IN {ACTIVE} AND {USABLE}"""),
    ("Items with a usable map point", "SELECT COUNT(DISTINCT p.entity_id) FROM v_entity_point p JOIN entity e ON e.entity_id=p.entity_id WHERE e.kind='item'"),
    ("Items reachable from a continent", """SELECT COUNT(DISTINCT g.entity_id) FROM v_geo_closure g JOIN entity p ON p.entity_id=g.place_id
         AND json_extract(p.attributes,'$.place_type')='continent' JOIN entity e ON e.entity_id=g.entity_id WHERE e.kind='item'"""),
    ("Items on >1 continent", """SELECT COUNT(*) FROM (SELECT g.entity_id FROM v_geo_closure g JOIN entity p ON p.entity_id=g.place_id
         AND json_extract(p.attributes,'$.place_type')='continent' JOIN entity e ON e.entity_id=g.entity_id WHERE e.kind='item'
         GROUP BY g.entity_id HAVING COUNT(DISTINCT g.place_id) > 1)"""),
    ("Date/coordinate claims resting only on Wikipedia", """SELECT COUNT(*) FROM claim c WHERE c.statement_type IN ('temporal','location')
         AND EXISTS (SELECT 1 FROM claim_evidence e WHERE e.claim_id=c.claim_id AND e.source_id='src:wikipedia-en')
         AND NOT EXISTS (SELECT 1 FROM claim_evidence e WHERE e.claim_id=c.claim_id AND e.source_id<>'src:wikipedia-en')"""),
    ("Claims with ≥2 distinct sources", "SELECT COUNT(*) FROM (SELECT claim_id FROM claim_evidence GROUP BY claim_id HAVING COUNT(DISTINCT source_id) >= 2)"),
    ("Claims citing institutional / literature sources", """SELECT COUNT(DISTINCT claim_id) FROM claim_evidence
         WHERE source_id NOT IN ('src:wikidata','src:wikipedia-en','src:gc-editorial','src:pleiades')"""),
    ("Items citing institutional / literature sources", """SELECT COUNT(DISTINCT c.entity_id) FROM claim c JOIN claim_evidence e ON e.claim_id=c.claim_id
         JOIN entity x ON x.entity_id=c.entity_id WHERE x.kind='item'
         AND e.source_id NOT IN ('src:wikidata','src:wikipedia-en','src:gc-editorial','src:pleiades')"""),
    ("Temporal extents with 'years ago' basis", "SELECT COUNT(*) FROM temporal_extent WHERE time_basis='years_before_source'"),
]


def main():
    dbs = [a.split("=", 1) for a in sys.argv[1:]]
    cons = [(lbl, sqlite3.connect(path)) for lbl, path in dbs]
    print("| metric | " + " | ".join(l for l, _ in cons) + " |")
    print("|---|" + "---|" * len(cons))
    for name, sql in METRICS:
        vals = []
        for _, con in cons:
            try:
                vals.append(str(con.execute(sql).fetchone()[0]))
            except sqlite3.Error:
                vals.append("n/a")
        print(f"| {name} | " + " | ".join(vals) + " |")
    print()
    print("Continent coverage (Items per continent):")
    print()
    print("| continent | " + " | ".join(l for l, _ in cons) + " |")
    print("|---|" + "---|" * len(cons))
    conts = set()
    data = []
    for _, con in cons:
        d = dict(con.execute("""SELECT p.canonical_name, COUNT(DISTINCT g.entity_id) FROM v_geo_closure g JOIN entity p ON p.entity_id=g.place_id
                                AND json_extract(p.attributes,'$.place_type')='continent' JOIN entity e ON e.entity_id=g.entity_id
                                WHERE e.kind='item' GROUP BY 1"""))
        conts |= set(d)
        data.append(d)
    for c in sorted(conts):
        print(f"| {c} | " + " | ".join(str(d.get(c, 0)) for d in data) + " |")
    print()
    print("Temporal coverage (Items whose preferred-or-any usable active extent starts in the bucket):")
    print()
    buckets = [("before 10,000 BCE", -1e18, -9999), ("10,000–3001 BCE", -9999, -3000), ("3000–1001 BCE", -3000, -1000),
               ("1000–1 BCE", -1000, 0), ("1–1000 CE", 0, 1000), ("1001–1900 CE", 1000, 1900)]
    print("| bucket | " + " | ".join(l for l, _ in cons) + " |")
    print("|---|" + "---|" * len(cons))
    for name, lo, hi in buckets:
        vals = []
        for _, con in cons:
            try:
                vals.append(str(con.execute(f"""SELECT COUNT(*) FROM (SELECT t.entity_id, MIN(COALESCE(t.earliest_start, t.latest_start)) AS s
                    FROM temporal_extent t JOIN claim c ON c.claim_id=t.claim_id JOIN entity e ON e.entity_id=t.entity_id
                    WHERE e.kind='item' AND t.role IN {ACTIVE} AND {USABLE} GROUP BY t.entity_id) WHERE s > ? AND s <= ?""",
                                            (lo, hi)).fetchone()[0]))
            except sqlite3.Error:
                vals.append("n/a")
        print(f"| {name} | " + " | ".join(vals) + " |")


if __name__ == "__main__":
    main()
