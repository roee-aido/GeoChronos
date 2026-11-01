"""Validation for the night-run expansion (build profile 'full').

The 37 base checks in validate.py stay tied to the 57-Item base seed. This suite checks what the
expansion adds (new kinds of data and edge cases) and re-runs the base suite against the full DB
for information, reporting — not hiding — any result that changes because new Items were added.

Usage:  python scripts/validate_expansion.py [--db build/geochronos.sqlite]
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import geoquery as gq  # noqa: E402
import timefmt as tf  # noqa: E402
import validate as base  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "build" / "validation_expansion_report.md"
I = base.I  # noqa: E741


def run(db=None):
    db = db or gq.DB_PATH
    con = gq.connect(db)
    s = base.Suite(con)
    TCOLS = ["canonical_name", "role", "label", "civil", "bp", "hebrew", "status", "open_ended"]
    s.md += ["# GeoChronos expansion validation report", "", f"DB: `{pathlib.Path(db).name}` (profile full)", ""]

    n_items = con.execute("SELECT COUNT(*) FROM entity WHERE kind='item'").fetchone()[0]
    s.assert_true("Item count within the night's ceiling (≤150)", n_items <= 150, f"{n_items} Items")
    dup = con.execute("""SELECT COUNT(*) FROM (SELECT value FROM external_id WHERE authority='wikidata'
                         GROUP BY value HAVING COUNT(DISTINCT entity_id) > 1)""").fetchone()[0]
    s.assert_true("No Wikidata QID mapped to two entities", dup == 0, f"{dup} duplicates")

    s.md += ["## Deep time", ""]
    s.check("4–3 million years ago (Ma precision)", gq.time_overlap(con, 1950 - 4_000_000, 1950 - 3_000_000),
            must_include=I("laetoli", "lucy-al-288-1"), columns=TCOLS)
    s.check("70–60 million years ago", gq.time_overlap(con, 1950 - 70_000_000, 1950 - 60_000_000),
            must_include=I("chicxulub-crater"), columns=TCOLS)
    s.check("80,000–70,000 years ago (events)", gq.time_overlap(con, 1950 - 80000, 1950 - 70000, kinds=("event",)),
            must_include={"event:youngest-toba-eruption"}, columns=TCOLS)

    s.md += ["## Rejected vs disputed claims", ""]
    s.check("Tiwanaku is NOT placed in 1600–1500 BC (the 1580 BC date is rejected)", gq.time_overlap(con, -1600, -1500),
            must_exclude=I("tiwanaku"), columns=TCOLS)
    rej = con.execute("""SELECT COUNT(*) FROM claim c JOIN temporal_extent t ON t.claim_id=c.claim_id
                         WHERE t.entity_id='item:tiwanaku' AND c.status='rejected'""").fetchone()[0]
    s.assert_true("…but the rejected claim is kept for audit", rej == 1, f"{rej} rejected claim(s) on Tiwanaku")
    sm = gq.dispute(con, "serpent-mound:date")
    s.assert_true("Serpent Mound: two disputed construction dates kept (300 BCE / c. 1070 CE)",
                  len(sm) == 2 and all(r["status"] == "disputed" for r in sm), "; ".join(r["temporal_label"] for r in sm))
    td = gq.dispute(con, "tel-dan:author")
    s.assert_true("Tel Dan stele: three competing author attributions, none preferred",
                  len(td) == 3 and not any(r["rank"] == "preferred" for r in td), ", ".join(r["object_id"] for r in td))

    s.md += ["## POV-First on new facets", ""]
    s.check("Show mosques (function, incl. time-scoped function)", gq.pov(con, "concept:function:mosque"),
            must_include=I("great-mosque-of-djenne", "hagia-sophia"), columns=["canonical_name", "via"])
    hq = con.execute("""SELECT r.qualifiers FROM relation r WHERE r.subject_id='item:hagia-sophia'
                        AND r.object_id='concept:function:museum'""").fetchone()
    s.assert_true("Hagia Sophia 'museum' function carries its period (1935–2020) as a qualifier",
                  hq and '"from": 1935' in hq[0] and '"to": 2020' in hq[0], hq[0] if hq else "missing")
    s.check("Theme: inscriptions and the Hebrew Bible", gq.pov(con, "concept:theme:biblical-archaeology"),
            must_include=I("mesha-stele", "tel-dan-stele", "siloam-inscription"), columns=["canonical_name", "via"])
    s.check("Architectural style imported from Wikidata P149 (Doric order)", gq.pov(con, "concept:style:doric-order", predicates=("has_style",)),
            must_include=I("parthenon"), columns=["canonical_name", "via"])
    s.check("Combined: Levant + text + 1000–500 BCE",
            gq.combined(con, "place:region:levant", "concept:type:text", (-1000, -500)),
            must_include=I("mesha-stele", "tel-dan-stele", "siloam-inscription"), must_exclude=I("dead-sea-scrolls"),
            columns=["canonical_name", "civil", "status"])

    s.md += ["## GEO: political vs geographic placement", ""]
    tp = {r["entity_id"]: r for r in gq.geo_in_place(con, "place:continent:europe")}
    s.assert_true("Taputapuātea reaches 'Europe' only on a political basis (France) — basis is visible",
                  "item:taputapuatea-marae" in tp and "political" in tp["item:taputapuatea-marae"]["bases"]
                  and "historical/cultural" not in tp["item:taputapuatea-marae"]["bases"],
                  tp.get("item:taputapuatea-marae", {}).get("bases", "not reached"))
    s.check("Africa now includes the new African Items", gq.geo_in_place(con, "place:continent:africa"),
            must_include=I("obelisk-of-aksum", "great-mosque-of-djenne", "kilwa-kisiwani", "leptis-magna", "laetoli"))

    s.md += ["## Time representation edge cases", ""]
    temple = gq.dispute(con, "jerusalem-70:temple-day")
    s.assert_true("70 CE Temple destruction: month of Av / 10 Av (Josephus) / 9 Av (commemoration) kept, no Julian day computed",
                  len(temple) == 3 and all(r["jdn_start"] is None for r in temple), "; ".join(r["temporal_label"] for r in temple))
    ros = dict(con.execute("""SELECT t.* FROM temporal_extent t JOIN claim c ON c.claim_id=t.claim_id
                              WHERE t.entity_id='item:rosetta-stone' AND t.precision='day' AND t.role='creation'""").fetchone())
    las = dict(con.execute("SELECT * FROM temporal_extent WHERE entity_id='item:lascaux-cave' AND role='discovery'").fetchone())
    s.assert_true("Hebrew rendering before 1178 CE is flagged as proleptic; modern dates are not",
                  "proleptically" in tf.format_hebrew(ros) and "proleptically" not in tf.format_hebrew(las),
                  f"{tf.format_hebrew(ros)} | {tf.format_hebrew(las)}")
    mv = dict(con.execute("""SELECT * FROM temporal_extent WHERE entity_id='item:monte-verde' AND label LIKE 'Monte Verde I re-dated%'""").fetchone())
    blo = dict(con.execute("""SELECT * FROM temporal_extent WHERE entity_id='item:blombos-cave' AND label LIKE 'c. 101,000%'""").fetchone())
    s.assert_true("Explicit 'BP' sources render as BP; 'years ago' sources do not", mv["time_basis"] == "bp_1950"
                  and blo["time_basis"] == "years_before_source" and " BP" in tf.format_bp(mv) and " BP" not in tf.format_bp(blo),
                  f"{tf.format_bp(mv)} | {tf.format_bp(blo)}")
    ai = con.execute("""SELECT COUNT(*) FROM entity_name n JOIN claim c ON c.claim_id=n.claim_id
                        WHERE c.note LIKE 'AI translation%' AND c.status <> 'needs_verification'""").fetchone()[0]
    he = con.execute("SELECT COUNT(DISTINCT entity_id) FROM entity_name WHERE lang='he'").fetchone()[0]
    s.assert_true("AI-supplied Hebrew names are never presented as verified", ai == 0, f"{he} entities have Hebrew names; {ai} unflagged AI names")

    passed = sum(ok for _, ok, _ in s.results)
    s.md[4:4] = ["", f"**{passed}/{len(s.results)} expansion checks passed.**", ""]
    REPORT.write_text("\n".join(s.md) + "\n", encoding="utf-8")
    for name, ok, problems in s.results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {problems}"))
    print(f"\n{passed}/{len(s.results)} expansion checks passed. Report: build/validation_expansion_report.md")

    # informational: the base suite on the full DB
    print("\n--- base suite on the FULL database (informational) ---")
    base_ok = base.run(db, ROOT / "build" / "validation_base_on_full_report.md")
    return passed == len(s.results), base_ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    a = ap.parse_args()
    exp_ok, _ = run(a.db)
    sys.exit(0 if exp_ok else 1)
