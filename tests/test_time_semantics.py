"""Brief §2.2 — four bounds: ordering, possible vs certain, NULL / open ends, roles, unknown time."""
import sqlite3
import unittest

from helpers import gq, scratch_copy


def add_extent(con, eid, role, es, ls, ee, le, label):
    cid = f"clm_test_{label}"
    con.execute("INSERT OR IGNORE INTO entity (entity_id, kind, canonical_name, created_at, updated_at) VALUES (?,?,?,?,?)",
                (eid, "item", eid, "t", "t"))
    con.execute("INSERT INTO claim (claim_id, entity_id, statement_type, confidence, recorded_by, recorded_at)"
                " VALUES (?,?,?,?,?,?)", (cid, eid, "temporal", "medium", "test", "t"))
    con.execute("INSERT INTO claim_evidence (claim_id, source_id) VALUES (?, 'src:gc-editorial')", (cid,))
    con.execute("INSERT INTO temporal_extent (entity_id, role, earliest_start, latest_start, earliest_end, latest_end,"
                " precision, label, claim_id) VALUES (?,?,?,?,?,?,?,?,?)", (eid, role, es, ls, ee, le, "year", label, cid))
    con.commit()


def ids(rows):
    return {r["entity_id"] for r in rows}


class TimeSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = con = scratch_copy()
        # astronomical years; query windows below are HISTORICAL years
        add_extent(con, "item:t-exact", "use", -999, -999, -899, -899, "exact")          # 1000–900 BCE
        add_extent(con, "item:t-fuzzy", "use", -1099, -999, -949, -899, "fuzzy")         # start 1100–1000, end 950–900 BCE
        add_extent(con, "item:t-open-end", "use", -1999, -1999, None, None, "openend")   # from 2000 BCE, end unknown
        add_extent(con, "item:t-open-start", "use", None, None, -499, -499, "openstart") # start unknown, until 500 BCE
        add_extent(con, "item:t-discovery", "discovery", 1900, 1900, 1900, 1900, "disc")

    def q(self, s, e, **kw):
        return ids(gq.time_overlap(self.con, s, e, **kw))

    def test_bound_order_enforced_by_schema(self):
        with self.assertRaises(sqlite3.IntegrityError):
            add_extent(self.con, "item:t-bad", "use", -500, -400, -600, -300, "bad")    # earliest_end < earliest_start
        self.con.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            add_extent(self.con, "item:t-bad2", "use", -500, -100, -600, -200, "bad2")  # latest_start > latest_end
        self.con.rollback()

    def test_possible_vs_certain(self):
        self.assertIn("item:t-exact", self.q(-950, -950))
        self.assertIn("item:t-exact", self.q(-950, -950, mode="certain"))
        self.assertIn("item:t-fuzzy", self.q(-1050, -1040))                        # could have started by then
        self.assertNotIn("item:t-fuzzy", self.q(-1050, -1040, mode="certain"))     # not certainly started
        self.assertIn("item:t-fuzzy", self.q(-990, -960, mode="certain"))          # inside [latest_start, earliest_end]

    def test_open_end_evidence_vs_unbounded(self):
        self.assertNotIn("item:t-open-end", self.q(-1500, -1500))                  # default: only as far as evidence
        self.assertIn("item:t-open-end", self.q(-1500, -1500, open_end="unbounded"))
        self.assertNotIn("item:t-open-end", self.q(-1500, -1500, mode="certain"))
        row = [r for r in gq.time_overlap(self.con, -1500, -1500, open_end="unbounded") if r["entity_id"] == "item:t-open-end"][0]
        self.assertTrue(row["open_ended"])

    def test_open_start_symmetric(self):
        self.assertNotIn("item:t-open-start", self.q(-1000, -1000))
        self.assertIn("item:t-open-start", self.q(-1000, -1000, open_end="unbounded"))
        self.assertIn("item:t-open-start", self.q(-500, -500))                      # the attested bound itself
        row = [r for r in gq.time_overlap(self.con, -500, -500) if r["entity_id"] == "item:t-open-start"][0]
        self.assertTrue(row["open_start"])

    def test_roles_default_exclude_heritage_history(self):
        self.assertNotIn("item:t-discovery", self.q(1900, 1900))
        self.assertIn("item:t-discovery", self.q(1900, 1900, roles=("discovery",)))

    def test_unknown_time_is_listed_not_dropped(self):
        unknown = ids(gq.time_unknown(self.con))
        self.assertIn("item:ahu-tongariki", unknown)
        self.assertIn("item:t-discovery", unknown)
        self.assertNotIn("item:great-pyramid-of-giza", unknown)

    def test_year_zero_boundary(self):
        add_extent(self.con, "item:t-1bce", "use", 0, 0, 0, 0, "onebce")               # astronomical 0 = 1 BCE
        self.assertIn("item:t-1bce", self.q(-1, -1))
        self.assertNotIn("item:t-1bce", self.q(1, 1))


if __name__ == "__main__":
    unittest.main()
