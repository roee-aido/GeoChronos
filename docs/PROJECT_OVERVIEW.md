# GeoChronos — Project Overview

A short map of the project for a new reader: what it is for, where things are, how data flows through it, and where it stands today. For how to run it, see the [Quickstart in the README](../README.md#quickstart).

## 1. Purpose

GeoChronos explores **PLACE × TIME × INFORMATION**: it connects places, historical events, artefacts and other entities across space and time, while keeping the source, the uncertainty and any competing claims behind every fact.

The same knowledge base has to answer questions from three starting points:

| Starting point | Example question |
|---|---|
| **GEO-First** | What is (transitively) inside this place? |
| **TIME-First** | What existed, or possibly existed, at a given time? |
| **POV-First** | Everything that shares a culture, function, religion, period or other point of view |

This repository is the **data foundation** (a proof of concept). It has no user interface yet.

## 2. Project structure

| Path | Role |
|---|---|
| `README.md` | Entry point: contents, quickstart, key assumptions, open questions, recommended next step |
| `DATA_ARCHITECTURE.md` | Recommended target architecture (PostgreSQL + PostGIS, relational knowledge graph + JSONB + claims), alternatives, scalability |
| `DATA_MODEL.md` | Entities, relationships, time and geo representation, provenance model, example records |
| `DATA_SOURCES.md`, `data/source_catalog.csv` | Source landscape, licensing and reliability; a catalogue of candidate sources |
| `QUERY_EXAMPLES.md` | GEO / TIME / POV / combined SQL examples; the blocks marked `-- test:` are executed by the test suite |
| `db/schema.sql` | Physical schema (SQLite for the POC, written to be portable to PostgreSQL) |
| `data/seed/` | Hand-curated input: Items, vocabulary, Wikidata targets, sources, literature, Wikipedia evidence, manual curation rows |
| `data/raw/` | Immutable source snapshots, each with a `MANIFEST.json` (Wikidata, Pleiades, Hebcal fixtures, Wikidata EntityData files) |
| `data/staging/` | Normalised JSONL, one file per snapshot, regenerable from `data/raw/` |
| `scripts/` | Ingestion, build, query, validation and reporting tools (Python standard library only) |
| `tests/` | `unittest` suite |
| `build/runs/2026-10-01_night/` | Published reports from the 2026-10-01 night run (quality, ingestion, tests, seed diff, curation queue) |
| `build/` (everything else) | Generated output; ignored by Git |

The schema has 11 tables (`source`, `entity`, `claim`, `claim_evidence`, `entity_name`, `external_id`, `location`, `temporal_extent`, `predicate`, `relation`, `entity_tag`) and 5 views (`v_temporal_claims`, `v_relation_claims`, `v_hierarchy`, `v_geo_closure`, `v_entity_point`).

## 3. Data workflow

```
 external sources            immutable snapshot           normalised            database
 (Wikidata, Pleiades)  ──►  data/raw/<source>/<time>/ ──►  data/staging/  ──►  build/*.sqlite
       scripts/ingest.py      + MANIFEST.json              *.jsonl            scripts/build_db.py
                                                                                     ▲
                              hand-curated seed: data/seed/*.json  ──────────────────┘

 build/*.sqlite ──► scripts/validate.py, scripts/validate_expansion.py, tests/  (checks)
                └─► scripts/geoquery.py  (GEO / TIME / POV query functions)
```

1. **Ingest** (`scripts/ingest.py wikidata|pleiades`, network). Each run writes a **new** snapshot folder and never overwrites an old one. `ingest.py status` lists the snapshots.
2. **Stage.** Raw responses are normalised to JSONL in `data/staging/`.
3. **Build** (`scripts/build_db.py --profile base|full`, offline). The seed and the staged data are mapped to **claims**. Every claim has at least one evidence row that points to a source (checked by the tests). Disagreements are kept as disputed or alternative claims, not resolved silently.
4. **Check.** `validate.py` (37 checks, base database), `validate_expansion.py` (20 checks, full database) and the `unittest` suite (40 tests). `scripts/run_suite.py` runs all of them and logs every step.

Two key modelling rules shape this flow:

- **Time.** Each time is stored as astronomical years with four uncertainty bounds. Calendars (CE/BCE, BP, Hebrew AM) are computed for display, never stored.
- **Wikidata.** It is the identity backbone, but it is not treated as an authority: its values arrive as `medium`-confidence claims.

## 4. Current state (as of 2026-11-01)

**What works.** These figures come from a fresh clone of this repository with Python 3.12.10:

| Profile | Items | Entities | Result |
|---|---|---|---|
| base (regression set) | 57 | 428 | `validate.py` 37/37 |
| full (base + expansion) | 95 | 632 | `validate_expansion.py` 20/20; base checks also 37/37 on it |

- The full database holds 3,579 claims and 6,097 evidence rows. 50 groups of competing claims are preserved, and 131 claims are marked `needs_verification`.
- The `unittest` suite passes: 40 tests.
- The build and the tests run offline, using only the Python standard library.

**What is not done yet** (see the README, *Recommended next step*):

- The schema has not been ported to PostgreSQL + PostGIS. That is the target; the POC runs on SQLite.
- Stage A ingestion has not been run: Wikidata for all UNESCO cultural properties, PeriodO periods, and Getty AAT concepts.
- Key claims that rest only on Wikipedia or abstracts are still waiting to be upgraded to primary or secondary literature. The curation queue lists them.
- There is no user interface.

**Open decisions.** These are listed in the README under *Open questions for GeoChronos spec*. They include Item granularity, the default meaning of "exists at time T", Hebrew display before AM 1, contested territories and the minimum evidence standard. None of them has been decided. The working choices made in the POC are listed under *Key assumptions* and are reversible.

**Kept outside the repository.** These stay local:

- the OpenAlex raw responses (they contain researcher e-mail addresses and abstracts)
- internal working notes
- local backups
- the HTTP cache
- generated databases
