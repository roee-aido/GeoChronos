# GeoChronos — Data Foundation (POC)

GeoChronos explores **PLACE × TIME × INFORMATION**. This folder contains the data foundation: architecture, data model, source map, a provenance-first seed dataset of real Items, and a runnable validation suite that proves **GEO-First**, **TIME-First** and **POV-First** exploration over one shared knowledge base.

> **Night run 2026-10-01:** the published reports are in [build/runs/2026-10-01_night/](build/runs/2026-10-01_night/): [CHECKPOINT.md](build/runs/2026-10-01_night/CHECKPOINT.md), [DATA_QUALITY_REPORT.md](build/runs/2026-10-01_night/DATA_QUALITY_REPORT.md), [INGESTION_REPORT.md](build/runs/2026-10-01_night/INGESTION_REPORT.md), [TESTS_ADDED.md](build/runs/2026-10-01_night/TESTS_ADDED.md), [SEED_DIFF.md](build/runs/2026-10-01_night/SEED_DIFF.md) and [CURATION_QUEUE.csv](build/runs/2026-10-01_night/CURATION_QUEUE.csv). Internal working notes (handoff, night report, spec inputs) are kept outside the repository.

## Contents

| Path | What it is |
|---|---|
| [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md) | Recommended architecture (PostgreSQL + PostGIS, relational knowledge graph + JSONB + claims), alternatives, scalability, extensibility |
| [DATA_MODEL.md](DATA_MODEL.md) | Entities, fields, relationships, time & geo representation, provenance model, example records (§9: night-run implementation details) |
| [DATA_SOURCES.md](DATA_SOURCES.md) | Source landscape, licensing, reliability, ingestion strategy |
| [data/source_catalog.csv](data/source_catalog.csv) | 80 candidate sources × 22 attributes (3 added 2026-10-01 night; verification column says what was actually checked) |
| [QUERY_EXAMPLES.md](QUERY_EXAMPLES.md) | GEO / TIME / POV / combined queries; every `-- test:` SQL block is executed by the test suite |
| [db/schema.sql](db/schema.sql) | Physical schema (SQLite POC, PostgreSQL-portable) + views |
| `data/seed/` | Curated seed. **Base (regression) set:** `items.json`, `vocabulary.json`, `wikidata_targets.json`. **Expansion:** `items_expansion.json`, `vocabulary_expansion.json`, `wikidata_targets_expansion.json`. Plus `sources.json`, `literature.json`, `wikipedia_evidence.json`, `curation_manual.csv` |
| `data/raw/` | Untouched snapshots with `MANIFEST.json` (Wikidata, Pleiades, OpenAlex, Hebcal fixtures, Wikidata EntityData calibration files); the 2026-09-30 legacy snapshot is kept as-is |
| `data/staging/` | Normalised JSONL per snapshot (re-generable from raw) |
| `scripts/` | `ingest.py` (fetch → raw → staging), `build_db.py` (mapping → claims/evidence), `geoquery.py`, `validate.py` (base), `validate_expansion.py` (full), `timefmt.py`, `curation_queue.py`, `run_suite.py`, `sparql/*.rq`; `fetch_wikidata.py` / `.ps1` are the older single-snapshot fetchers |
| `tests/` | `unittest` suite: claim filters, time semantics, calendars (incl. Hebcal fixtures), provenance, identity, idempotent re-import, SQL-example equivalence |
| `build/` (generated) | `geochronos_base.sqlite` (57 Items), `geochronos.sqlite` (full, 95 Items), build/validation reports, `runs/` |

## Run it

Requires Python 3.10+ (standard library only; no pip packages). On Windows, `py` works too.

```bash
python scripts/run_suite.py --out build/runs/manual --steps timefmt,build,build-full,validate,tests
```

That one command runs the steps below and records command, time, time zone, exit code and output. Individually:

```bash
python scripts/build_db.py --profile base
```

```bash
python scripts/build_db.py --profile full
```

```bash
python scripts/validate.py
```

```bash
python scripts/validate_expansion.py
```

```bash
python -m unittest discover -s tests -v
```

Refreshing sources (network; writes a NEW immutable snapshot, never overwrites one):

```bash
python scripts/ingest.py wikidata --dry-run
```

```bash
python scripts/ingest.py wikidata
```

```bash
python scripts/ingest.py pleiades
```

## Key assumptions (explicit)

1. **"Item" is one kind of entity, not the only one.** Places, periods, cultures, persons, events, religions and concepts are first-class entities, so that POV-First can pivot on any of them. This extends the brief (Item as the fundamental entity) without contradicting it.
2. **Time is stored as astronomical years with four uncertainty bounds.** Display calendars (CE/BCE, BP, Hebrew AM) are computed. Where a source gives "X years ago", the POC stores it relative to 1950 (BP convention); the difference is far below the precision of such dates.
3. **Wikidata is the identity backbone but not an authority.** Its values are imported as claims (confidence `medium`). Obvious errors are kept but flagged, never deleted.
4. **English Wikipedia was used to verify dates in the POC.** It is a tertiary source: claims resting only on it are `medium` confidence at best. Each claim cites the exact revision ID, so a reviewer can see exactly what was read. Upgrading key claims to primary/secondary literature is a next step.
5. **UNESCO text and boundaries were not used**, because the UNESCO site blocked automated access and its reuse licence is unverified. Only UNESCO property IDs (via Wikidata) are stored.
6. **Classification facets (form, function, culture …) are curatorial decisions.** They are based on the cited source's description and labelled as such in each claim note.
7. **"Neolithic" and "Bronze Age" deliberately have no global dates.** They are region-dependent; region-specific periods (e.g. PPNA, Egyptian Old Kingdom) carry dates.
8. **Modern political geography comes from Wikidata as-is**, including for contested areas (e.g. Wikidata's P17/P131 values for Qumran and Tell es-Sultan). It is stored as claims, not endorsed. The UI will need a neutral presentation policy (see open questions).
9. **Night-run working choices (reversible, not Roee's decisions):**
   - TIME defaults to `possible` overlap with `open_end='evidence'`.
   - Movable-object coordinates count as find spots only within 5 km of the Wikidata P189 location of discovery.
   - Hebrew AM renderings before 1178 CE are labelled 'computed proleptically'.
   - Biological taxa sit in the culture facet for now.

## OPEN QUESTIONS FOR GEOCHRONOS SPEC

> The night run found further questions in the actual data; they are tracked in the internal working notes (not in this repository) and in [CURATION_QUEUE.csv](build/runs/2026-10-01_night/CURATION_QUEUE.csv). No decision has been taken on any of them.

Decisions that should be made **before** expanding beyond the POC:

**Scope & granularity**
1. **Item granularity.** What is one Item?
   - Candidates for one-vs-many: a complex (Giza), a structure (Great Pyramid), a phase (Stonehenge sarsen circle), a find (one Dead Sea Scroll vs. "the scrolls").
   - Proposal: allow all levels, linked by `part_of`, but define which level appears by default on the map at each zoom.
2. **Object vs site.** Should movable objects appear on the map by find spot, by current museum, or both, with a toggle?
3. **Inclusion criteria.** UNESCO-only? All Wikidata "archaeological site" instances (hundreds of thousands, uneven quality)? A minimum evidence threshold?

**Time**
4. **Default meaning of "exists at time T".**
   - Options: built, in use, or still standing. The POC uses "active roles" (construction/use/occupation/event).
   - Should the default instead be "possible" or "certain" overlap?
5. **Hebrew calendar before AM 1 (3761 BCE).**
   - Options: show "before Creation (traditional reckoning)", show negative AM, or fall back to civil/BP.
   - This affects most prehistoric Items and should be decided with the intended audience in mind.
6. **Which chronology is the default?** For Egypt (Shaw vs others), Mesopotamia (short/middle chronology) and the Aegean (Thera high/low). Should the user be able to switch chronologies globally?
7. **Period authority.** Adopt PeriodO as the canonical period registry? How are competing definitions presented?

**Geography & sensitivity**
8. **Contested territories and names.** For Jerusalem, the West Bank, and other disputed borders:
   - Show modern political attribution at all?
   - Use a neutral historical-region layer by default?
   - How are names presented in Hebrew / Arabic / English?
9. **Transcontinental and political-vs-geographic placement.** Two examples:
   - Turkey (Anatolia vs. Europe).
   - Rapa Nui, which is politically Chile (South America) but geographically Polynesia (Oceania). The POC build flags this case.

   Proposal: continent membership via point-in-polygon (Natural Earth), not via country.
10. **Sensitive site locations.** What is the policy for looted or endangered sites, unpublished coordinates, and Indigenous cultural heritage (e.g. Budj Bim, Gunditjmara)? Options: precision reduction, consent, and cultural protocols.

**Evidence & governance**
11. **Minimum evidence standard.** Must every public claim cite a primary or secondary scholarly source, or is Wikidata/Wikipedia acceptable for display with a visible confidence badge?
12. **Who may add or curate claims?** Options: curator-only, expert contributors, or public suggestions, with a moderation workflow. How are `preferred` ranks decided, and by whom?
13. **How is uncertainty shown in the UI?** Examples: fuzzy timeline bars, "disputed" badges, a "show all versions" panel.

**Licensing & product**
14. **Commercial or non-commercial?** This determines whether NC-licensed sources (some maps, 3D, Seshat) can be used at all.
15. **ODbL (OpenStreetMap) share-alike.** Keep OSM-derived geometry in a separately-licensed layer, or avoid OSM geometry entirely?
16. **Languages.** Is Hebrew UI a first-class requirement from v1? That affects name sourcing (Kima, Wikidata `he` labels), RTL design and calendar defaults.
17. **Media and audio layer.** Is contextual audio/music in scope for v1? It needs per-file licence tracking from day one.

## Recommended next step

1. Decide open questions **1** (Item granularity), **4** (default meaning of "exists at T"), **5** (Hebrew display before AM 1), **8** (contested territories) and **11** (minimum evidence standard).
2. Port `db/schema.sql` to PostgreSQL + PostGIS. The notes at the top of the file list each type mapping.
3. Run **Stage A ingestion**:
   - Wikidata for all UNESCO cultural properties.
   - PeriodO for period entities.
   - Getty AAT for form, function and material concepts.

   Use the same snapshot → claims → evidence pipeline (see DATA_SOURCES.md §5).
4. Work through the curation queue in `build/build_report.md`, and upgrade Wikipedia-only claims for flagship Items to primary or secondary literature.
