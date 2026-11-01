"""Shared fixtures: build throw-away databases so tests never touch build/ outputs."""
import pathlib
import shutil
import sqlite3
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_db  # noqa: E402
import geoquery as gq  # noqa: E402

_CACHE = {}


def built_db(profile="base"):
    """Build once per test run per profile into a temp dir; return the path."""
    if profile not in _CACHE:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"gc_{profile}_"))
        b, _ = build_db.build(tmp / "db.sqlite", profile=profile, report_dir=tmp, quiet=True)
        assert not b.errors, b.errors
        _CACHE[profile] = (tmp / "db.sqlite", b)
    return _CACHE[profile][0]


def builder(profile="base"):
    built_db(profile)
    return _CACHE[profile][1]


def scratch_copy(profile="base"):
    """A private writable copy of a built DB (for tests that mutate claims)."""
    src = built_db(profile)
    dst = pathlib.Path(tempfile.mkdtemp(prefix="gc_scratch_")) / "db.sqlite"
    shutil.copy(src, dst)
    return gq.connect(dst)


def fingerprint(path):
    """Content fingerprint of a build: row counts + sorted keys of every table."""
    con = sqlite3.connect(path)
    fp = {}
    for t, key in (("entity", "entity_id"), ("claim", "claim_id || rank || status"),
                   ("claim_evidence", "claim_id || '|' || source_id || '|' || IFNULL(locator,'')"),
                   ("relation", "subject_id || predicate_id || object_id"),
                   ("location", "entity_id || role || lat || lon"),
                   ("temporal_extent", "claim_id"), ("entity_name", "entity_id || name || IFNULL(lang,'')"),
                   ("external_id", "entity_id || authority || value")):
        rows = [r[0] for r in con.execute(f"SELECT {key} FROM {t}")]
        fp[t] = (len(rows), tuple(sorted(rows)))
    con.close()
    return fp
