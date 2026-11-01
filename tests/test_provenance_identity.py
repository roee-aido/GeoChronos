"""Brief §2.4–2.6 — object locations, provenance completeness, identity, idempotent re-import."""
import json
import pathlib
import shutil
import sqlite3
import tempfile
import unittest

from helpers import ROOT, build_db, built_db, fingerprint, gq

OBJECTS = ("item:rosetta-stone", "item:venus-of-willendorf", "item:antikythera-mechanism", "item:dead-sea-scrolls",
           "item:mask-of-tutankhamun")


class ObjectLocationTests(unittest.TestCase):
    def setUp(self):
        self.con = gq.connect(built_db())

    def test_object_points_are_verified_or_inherited(self):
        for eid in OBJECTS:
            pts = self.con.execute("SELECT role, via, point_entity_id FROM v_entity_point WHERE entity_id=?", (eid,)).fetchall()
            self.assertTrue(pts, f"{eid} has no usable point")
            for p in pts:
                self.assertTrue(p["role"] == "find_spot" or p["via"] == "found_at",
                                f"{eid}: point must be a verified find spot or inherited from the find place, got {dict(p)}")

    def test_unverified_object_point_never_used(self):
        for (role,) in self.con.execute("SELECT DISTINCT role FROM v_entity_point"):
            self.assertIn(role, ("primary", "find_spot"))

    def test_find_spot_note_names_its_basis(self):
        for (note,) in self.con.execute("SELECT c.note FROM location l JOIN claim c ON c.claim_id=l.claim_id WHERE l.role='find_spot'"):
            self.assertIn("P189", note)

    def test_current_keeper_separate_from_location(self):
        held = {r["entity_id"] for r in gq.geo_currently_held_in(self.con, "place:city:london")}
        self.assertIn("item:rosetta-stone", held)
        self.assertNotIn("item:rosetta-stone", {r["entity_id"] for r in gq.geo_in_place(self.con, "place:city:london")})


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(built_db())

    def test_every_claim_has_evidence(self):
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM claim WHERE claim_id NOT IN (SELECT claim_id FROM claim_evidence)").fetchone()[0], 0)

    def test_every_fact_row_has_a_claim_with_a_real_source(self):
        for t in ("entity_name", "location", "temporal_extent", "relation"):
            self.assertEqual(self.con.execute(f"SELECT COUNT(*) FROM {t} WHERE claim_id NOT IN (SELECT claim_id FROM claim)").fetchone()[0], 0, t)
        n = self.con.execute("""SELECT COUNT(*) FROM claim c WHERE c.statement_type IN ('temporal','location') AND NOT EXISTS
                                (SELECT 1 FROM claim_evidence e WHERE e.claim_id=c.claim_id AND e.source_id<>'src:gc-editorial')""").fetchone()[0]
        self.assertEqual(n, 0)

    def test_external_ids_have_source(self):
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM external_id WHERE source_id IS NULL").fetchone()[0], 0)

    def test_no_automatic_high_confidence_for_imports(self):
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM claim WHERE recorded_by LIKE 'import:%' AND confidence='high'").fetchone()[0], 0)

    def test_wikidata_evidence_names_its_snapshot(self):
        bad = self.con.execute("SELECT COUNT(*) FROM claim_evidence WHERE source_id='src:wikidata' AND locator NOT LIKE '%@%'").fetchone()[0]
        self.assertEqual(bad, 0)

    def test_identity_unique(self):
        self.assertEqual(self.con.execute("""SELECT COUNT(*) FROM (SELECT value FROM external_id WHERE authority='wikidata'
                                             GROUP BY value HAVING COUNT(DISTINCT entity_id) > 1)""").fetchone()[0], 0)


class IdempotenceTests(unittest.TestCase):
    """Real re-import checks on throw-away staging copies."""

    def stage_copy(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="gc_staging_"))
        shutil.copytree(ROOT / "data" / "staging", d / "staging")
        return d / "staging"

    def build(self, staging):
        out = pathlib.Path(tempfile.mkdtemp(prefix="gc_idem_"))
        b, _ = build_db.build(out / "db.sqlite", "base", staging=staging, report_dir=out, quiet=True)
        self.assertFalse(b.errors, b.errors)
        return out / "db.sqlite", b

    def test_rebuild_same_staging_is_identical(self):
        st = self.stage_copy()
        self.assertEqual(fingerprint(self.build(st)[0]), fingerprint(self.build(st)[0]))

    def test_same_snapshot_staged_twice_creates_no_duplicates(self):
        st = self.stage_copy()
        a = fingerprint(self.build(st)[0])
        latest = sorted((st / "wikidata").glob("2026-10-01*.jsonl"))[-1]
        shutil.copy(latest, st / "wikidata" / ("zz_duplicate_of_" + latest.name))
        self.assertEqual(a, fingerprint(self.build(st)[0]))

    def test_identical_content_new_snapshot_adds_evidence_only(self):
        st = self.stage_copy()
        a = fingerprint(self.build(st)[0])
        latest = sorted((st / "wikidata").glob("2026-10-01*.jsonl"))[-1]
        lines = latest.read_text(encoding="utf-8").splitlines()
        meta = json.loads(lines[0])
        meta["_snapshot"]["snapshot_id"] = "2026-10-02T000000+0300-synthetic"
        meta["_snapshot"]["retrieved_at"] = "2026-10-02T00:00:00+03:00"
        (st / "wikidata" / "synthetic.jsonl").write_text("\n".join([json.dumps(meta)] + lines[1:]) + "\n", encoding="utf-8")
        db, _ = self.build(st)
        b = fingerprint(db)
        for t in ("entity", "relation", "location", "temporal_extent", "entity_name", "external_id"):
            self.assertEqual(a[t], b[t], t)                              # no duplicate fact rows
        self.assertGreater(b["claim_evidence"][0], a["claim_evidence"][0])  # one more evidence row per re-asserted claim
        self.assertEqual(sqlite3.connect(db).execute("SELECT COUNT(*) FROM claim WHERE rank='deprecated'").fetchone()[0],
                         sqlite3.connect(self.build(self.stage_copy())[0]).execute("SELECT COUNT(*) FROM claim WHERE rank='deprecated'").fetchone()[0])

    def test_changed_value_keeps_old_claim(self):
        st = self.stage_copy()
        latest = sorted((st / "wikidata").glob("2026-10-01*.jsonl"))[-1]
        lines = latest.read_text(encoding="utf-8").splitlines()
        meta = json.loads(lines[0])
        meta["_snapshot"]["snapshot_id"] = "2026-10-02T000000+0300-synthetic-change"
        meta["_snapshot"]["retrieved_at"] = "2026-10-02T00:00:00+03:00"
        out = [json.dumps(meta)]
        for line in lines[1:]:
            r = json.loads(line)
            if r["query"] == "core" and r["b"]["item"].endswith("/Q37200"):
                r["b"]["coords"] = "Point(31.2 29.9)"                     # synthetic change for the test only
            out.append(json.dumps(r, ensure_ascii=False))
        (st / "wikidata" / "synthetic_change.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")
        db, _ = self.build(st)
        con = sqlite3.connect(db)
        rows = con.execute("""SELECT l.lat, l.lon, c.rank, c.note FROM location l JOIN claim c ON c.claim_id=l.claim_id
                              WHERE l.entity_id='item:great-pyramid-of-giza' AND l.role='primary'""").fetchall()
        by = {(round(r[0], 4), round(r[1], 4)): r for r in rows}
        self.assertEqual(by[(29.9, 31.2)][2], "normal")
        old = [r for k, r in by.items() if k != (29.9, 31.2)]
        self.assertTrue(old and all(r[2] == "deprecated" and "kept for history" in r[3] for r in old))


if __name__ == "__main__":
    unittest.main()
