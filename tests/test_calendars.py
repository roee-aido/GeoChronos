"""Brief §2.3 — BCE without year 0 vs astronomical years, Wikidata precision/numbering, Julian/Gregorian,
JDN, BP (1950 base), Hebrew conversion checked against independent Hebcal output."""
import json
import pathlib
import unittest

from helpers import ROOT, build_db
import timefmt as tf

ENTITYDATA = ROOT / "data" / "raw" / "wikidata_entitydata_2026-10-01"
HEBCAL = sorted((ROOT / "data" / "raw" / "hebcal").glob("*"))


class YearNumberingTests(unittest.TestCase):
    def test_hist_astro(self):
        self.assertEqual(tf.hist_to_astro(-1), 0)
        self.assertEqual(tf.hist_to_astro(1), 1)
        self.assertEqual(tf.hist_to_astro(-2500), -2499)
        self.assertEqual(tf.astro_to_hist(0), (1, "BCE"))
        self.assertEqual(tf.astro_to_hist(-2499), (2500, "BCE"))
        with self.assertRaises(ValueError):
            tf.hist_to_astro(0)


class WikidataDateTests(unittest.TestCase):
    """Every (item, property) value calibrated on 2026-10-01: JSON (historical numbering) must equal the
    historical year our parser derives from the WDQS value, for every precision present."""

    def test_calibration_against_entitydata(self):
        legacy = json.loads((ROOT / "data" / "raw" / "wikidata_2026-09-30.json").read_text(encoding="utf-8"))
        rdf = {}
        for b in legacy["queries"]["time"]["results"]["results"]["bindings"]:
            rdf.setdefault((b["item"]["value"].rsplit("/", 1)[1], b["prop"]["value"]), []).append(b)
        checked = 0
        for f in ENTITYDATA.glob("Q*.json"):
            q = f.stem
            ent = json.loads(f.read_text(encoding="utf-8"))["entities"][q]
            for (qq, p), bs in rdf.items():
                if qq != q:
                    continue
                json_years = set()
                for st in ent["claims"].get(p, []):
                    v = st["mainsnak"]["datavalue"]["value"]
                    if st["rank"] != "deprecated":
                        json_years.add((int(v["time"][:v["time"].index("-", 1)]), v["precision"]))
                for b in bs:
                    parsed = build_db.wd_value_bounds(b["time"]["value"], b["precision"]["value"], b["calendar"]["value"])
                    prec = int(b["precision"]["value"])
                    if prec == 11:
                        continue                       # day values are Gregorian-normalised (date may shift)
                    self.assertIn((parsed["hist_year"], prec), json_years, f"{q} {p} {b['time']['value']}")
                    checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_precision_intervals_help_dates(self):
        cal = "http://www.wikidata.org/entity/Q1985786"
        c19 = build_db.wd_value_bounds("1848-01-01T00:00:00Z", 7, cal)                  # 19th century CE
        self.assertEqual((c19["lo"], c19["hi"]), (1801.0, 1900.0))
        b30 = build_db.wd_value_bounds("-3000-01-01T00:00:00Z", 7, cal)                 # 30th century BCE = 3000–2901 BCE
        self.assertEqual((b30["lo"], b30["hi"]), (-2999.0, -2900.0))
        m10 = build_db.wd_value_bounds("-9999-01-01T00:00:00Z", 6, cal)                 # 10th millennium BCE = 10000–9001 BCE
        self.assertEqual((m10["lo"], m10["hi"]), (-9999.0, -9000.0))
        d = build_db.wd_value_bounds("-0510-01-01T00:00:00Z", 8, cal)                   # the 510s BCE = 519–510 BCE
        self.assertEqual((d["lo"], d["hi"]), (-518.0, -509.0))
        y = build_db.wd_value_bounds("-1273-05-01T00:00:00Z", 10, cal)                  # month precision: already astronomical
        self.assertEqual((y["lo"], y["hist_year"]), (-1273.0, -1274))


class JdnTests(unittest.TestCase):
    def test_anchors(self):
        self.assertEqual(tf.jdn_from_date(2000, 1, 1), 2451545)
        self.assertEqual(tf.jdn_from_date(-4712, 1, 1, "julian"), 0)
        self.assertEqual(tf.fixed_from_julian(1582, 10, 4) + 1, tf.fixed_from_gregorian(1582, 10, 15))
        # Independent anchor from Wikidata (Q1421 Titus): JSON stores Julian 0039-12-30, WDQS returns the same day as
        # Gregorian 0039-12-28. In the 1st century the same day is labelled 2 days earlier in the Gregorian calendar.
        self.assertEqual(tf.fixed_from_julian(39, 12, 30), tf.fixed_from_gregorian(39, 12, 28))
        self.assertEqual(tf.fixed_from_julian(79, 8, 24) - tf.fixed_from_gregorian(79, 8, 24), -2)


class HebrewAgainstHebcalTests(unittest.TestCase):
    MONTHS = {"Nisan": 1, "Iyyar": 2, "Sivan": 3, "Tamuz": 4, "Av": 5, "Elul": 6, "Tishrei": 7, "Cheshvan": 8,
              "Kislev": 9, "Tevet": 10, "Sh'vat": 11, "Adar": 12, "Adar I": 12, "Adar II": 13}

    def test_against_hebcal_fixtures(self):
        self.assertTrue(HEBCAL, "no Hebcal fixture snapshot")
        n = 0
        for f in sorted(HEBCAL[-1].glob("g2h_*.json")):
            j = json.loads(f.read_text(encoding="utf-8"))
            ours = tf.hebrew_from_fixed(tf.fixed_from_gregorian(j["gy"], j["gm"], j["gd"]))   # Hebcal input is proleptic Gregorian
            self.assertEqual(ours, (j["hy"], self.MONTHS[j["hm"]], j["hd"]), f.name)
            n += 1
        self.assertGreaterEqual(n, 8)

    def test_self_test(self):
        self.assertTrue(tf.self_test())


class BpTests(unittest.TestCase):
    def test_1950_base(self):
        self.assertEqual(tf.format_bp({"earliest_start": 1950, "latest_end": 1950, "precision": "year"}), "0 cal BP")
        self.assertIn("not applicable", tf.format_bp({"earliest_start": 1960, "latest_end": 1960, "precision": "year"}))
        self.assertEqual(tf.format_bp({"earliest_start": -2699, "latest_end": -2499, "precision": "century"}), "4,649–4,449 cal BP")

    def test_years_ago_not_presented_as_bp(self):
        ext = {"earliest_start": 1950 - 101000, "latest_end": 1950 - 70000, "precision": "ka", "time_basis": "years_before_source"}
        txt = tf.format_bp(ext)
        self.assertNotIn(" BP", txt)
        self.assertIn("ago", txt)
        self.assertIn("1950", txt)


if __name__ == "__main__":
    unittest.main()
