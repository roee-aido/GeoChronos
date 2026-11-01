"""Brief §2.2 — SQL examples in QUERY_EXAMPLES.md must have the same semantics as geoquery.py.
Every ```sql block whose first line is '-- test: <name>' is executed and compared (entity sets)."""
import re
import unittest

from helpers import ROOT, built_db, gq

DOC = ROOT / "QUERY_EXAMPLES.md"

EXPECT = {
    "geo_in_egypt": lambda con: gq.geo_in_place(con, "place:country:egypt"),
    "geo_near_giza_20km": lambda con: gq.geo_near(con, 29.97915, 31.13422, 20),
    "time_2500_possible_evidence": lambda con: gq.time_overlap(con, -3000, -2000),
    "time_2500_certain": lambda con: gq.time_overlap(con, -3000, -2000, mode="certain"),
    "time_2500_possible_unbounded": lambda con: gq.time_overlap(con, -3000, -2000, open_end="unbounded"),
    "pov_pyramid": lambda con: gq.pov(con, "concept:form:pyramid"),
    "combined_egypt_tomb_3000_2000": lambda con: gq.combined(con, "place:country:egypt", "concept:function:tomb", (-3000, -2000)),
}


def blocks():
    text = DOC.read_text(encoding="utf-8")
    for body in re.findall(r"```sql\n(.*?)```", text, flags=re.S):
        m = re.match(r"--\s*test:\s*(\S+)\s*\n", body)
        if m:
            yield m.group(1), body


class QueryExamplesTests(unittest.TestCase):
    def test_every_tagged_block_matches_geoquery(self):
        found = set()
        for profile in ("base", "full"):
            con = gq.connect(built_db(profile))
            for name, sql in blocks():
                found.add(name)
                got = {r[0] for r in con.execute(sql)}
                if name in EXPECT:
                    want = {r["entity_id"] for r in EXPECT[name](con)}
                    self.assertEqual(got, want, f"{profile}: {name}")
                else:
                    self.assertTrue(got, f"{profile}: {name} returned nothing")
        self.assertTrue(set(EXPECT) <= found, f"untested expectations: {set(EXPECT) - found}")

    def test_postgis_sketches_are_marked(self):
        text = DOC.read_text(encoding="utf-8")
        for body in re.findall(r"```sql\n(.*?)```", text, flags=re.S):
            if "ST_" in body:
                self.assertIn("NOT EXECUTED", body)


if __name__ == "__main__":
    unittest.main()
