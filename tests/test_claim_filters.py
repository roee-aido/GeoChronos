"""Brief §2.1 — rejected/deprecated claims never reach ordinary results; disputed/alternative stay and are flagged.
Checked in locations, location inheritance, hierarchy (POV), GEO containment and combined queries."""
import unittest

from helpers import gq, scratch_copy


def set_claim(con, where_sql, args, **fields):
    cids = [r[0] for r in con.execute(f"SELECT claim_id FROM ({where_sql})", args)]
    assert cids, f"no claim matched: {where_sql} {args}"
    for k, v in fields.items():
        con.executemany(f"UPDATE claim SET {k}=? WHERE claim_id=?", [(v, c) for c in cids])
    con.commit()
    return cids


REL = "SELECT r.claim_id FROM relation r WHERE r.subject_id=? AND r.predicate_id=? AND r.object_id=?"
LOC = "SELECT l.claim_id FROM location l WHERE l.entity_id=? AND l.role='primary'"


class ClaimFilterTests(unittest.TestCase):
    def test_rejected_location_removes_map_point(self):
        con = scratch_copy()
        self.assertIn("item:great-pyramid-of-giza", {r["entity_id"] for r in gq.geo_near(con, 29.97915, 31.13422, 1)})
        set_claim(con, LOC, ("item:great-pyramid-of-giza",), status="rejected")
        self.assertNotIn("item:great-pyramid-of-giza", {r["entity_id"] for r in gq.geo_near(con, 29.97915, 31.13422, 1)})
        self.assertNotIn("item:great-pyramid-of-giza", {r["entity_id"] for r in gq.geo_bbox(con, 29.9, 31.0, 30.1, 31.3)})

    def test_deprecated_location_removes_map_point(self):
        con = scratch_copy()
        set_claim(con, LOC, ("item:great-pyramid-of-giza",), rank="deprecated")
        self.assertNotIn("item:great-pyramid-of-giza", {r["entity_id"] for r in gq.geo_near(con, 29.97915, 31.13422, 1)})

    def test_deprecated_part_of_stops_inheritance_and_containment(self):
        con = scratch_copy()
        pts = con.execute("SELECT via, point_entity_id FROM v_entity_point WHERE entity_id='item:tower-of-jericho'").fetchall()
        self.assertTrue(pts and all(p["via"] == "part_of" for p in pts), "Tower must inherit via part_of")
        set_claim(con, REL, ("item:tower-of-jericho", "part_of", "item:tell-es-sultan"), rank="deprecated")
        self.assertEqual(con.execute("SELECT COUNT(*) FROM v_entity_point WHERE entity_id='item:tower-of-jericho'").fetchone()[0], 0)
        self.assertNotIn("item:tower-of-jericho", {r["entity_id"] for r in gq.geo_in_place(con, "place:region:levant")})

    def test_rejected_located_in_removes_containment(self):
        con = scratch_copy()
        set_claim(con, REL, ("item:masada", "located_in", "place:region:judaean-desert"), status="rejected")
        levant = {r["entity_id"] for r in gq.geo_in_place(con, "place:region:levant")}
        self.assertNotIn("item:masada", levant)                       # only path to the curated Levant region
        self.assertIn("item:masada", {r["entity_id"] for r in gq.geo_in_place(con, "place:continent:asia")})  # via Israel

    def test_rejected_broader_cuts_hierarchy(self):
        con = scratch_copy()
        set_claim(con, REL, ("concept:form:step-pyramid", "broader", "concept:form:pyramid"), status="rejected")
        self.assertNotIn("item:pyramid-of-djoser", {r["entity_id"] for r in gq.pov(con, "concept:form:pyramid")})
        self.assertIn("item:pyramid-of-djoser", {r["entity_id"] for r in gq.pov(con, "concept:form:step-pyramid")})

    def test_rejected_facet_removed_from_combined(self):
        con = scratch_copy()
        set_claim(con, REL, ("item:great-pyramid-of-giza", "has_function", "concept:function:tomb"), status="rejected")
        res = {r["entity_id"] for r in gq.combined(con, "place:country:egypt", "concept:function:tomb", (-3000, -2000))}
        self.assertEqual(res, {"item:pyramid-of-djoser"})

    def test_rejected_temporal_claim_not_matched(self):
        con = scratch_copy()
        pref = con.execute("""SELECT t.claim_id, t.label FROM temporal_extent t JOIN claim c ON c.claim_id=t.claim_id
                              WHERE t.entity_id='item:great-pyramid-of-giza' AND c.rank='preferred'""").fetchone()
        set_claim(con, "SELECT ? AS claim_id", (pref["claim_id"],), status="rejected")
        rows = [r for r in gq.time_overlap(con, -3000, -2000) if r["entity_id"] == "item:great-pyramid-of-giza"]
        self.assertEqual(len(rows), 1)                               # still found through the other, non-rejected claims
        self.assertNotEqual(rows[0]["label"], pref["label"])

    def test_disputed_kept_and_flagged(self):
        con = scratch_copy()
        khufu = {r["entity_id"]: r for r in gq.pov_related_to(con, "person:khufu")}
        self.assertEqual(khufu["item:great-sphinx-of-giza"]["status"], "disputed")
        set_claim(con, REL, ("item:masada", "located_in", "place:region:judaean-desert"), status="disputed")
        levant = {r["entity_id"]: r for r in gq.geo_in_place(con, "place:region:levant")}
        self.assertIn("item:masada", levant)
        self.assertEqual(levant["item:masada"]["uncertain_only"], 1)
        set_claim(con, REL, ("item:tower-of-jericho", "part_of", "item:tell-es-sultan"), status="alternative")
        self.assertEqual(con.execute("SELECT MAX(uncertain) FROM v_entity_point WHERE entity_id='item:tower-of-jericho'").fetchone()[0], 1)

    def test_hierarchy_flags_uncertain_links(self):
        con = scratch_copy()
        set_claim(con, REL, ("concept:form:dolmen", "broader", "concept:form:megalith"), status="disputed")
        row = con.execute("SELECT uncertain_only FROM v_hierarchy WHERE descendant_id='concept:form:dolmen' "
                          "AND ancestor_id='concept:form:megalith'").fetchone()
        self.assertEqual(row[0], 1)
        meg = {r["entity_id"]: r for r in gq.pov(con, "concept:form:megalith")}
        self.assertIn("item:dolmen-of-menga", meg)                    # disputed links are kept, not dropped


if __name__ == "__main__":
    unittest.main()
