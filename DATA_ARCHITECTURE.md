# GeoChronos — Data Architecture

> Status: v0.1 (proof of concept) · Companion docs: [DATA_MODEL.md](DATA_MODEL.md), [DATA_SOURCES.md](DATA_SOURCES.md), [QUERY_EXAMPLES.md](QUERY_EXAMPLES.md)

## 1. What the data has to do

GeoChronos is a **PLACE × TIME × INFORMATION** exploration system. One knowledge base must answer three kinds of entry question equally well:

| Mode | Entry point | Typical question | Dominant operation |
|---|---|---|---|
| **GEO-First** | a place / map area | "What is in Upper Egypt, across all of time?" | spatial containment / proximity + hierarchy walk |
| **TIME-First** | a moment or span | "What existed around 2500 BCE ± 500?" | interval overlap on uncertain ranges |
| **POV-First** | a point of view: concept, type, culture, person, theme, relationship | "Show megalithic tombs", "Everything linked to Khufu" | graph traversal over typed relations + vocabulary hierarchy |

These are **three views over the same data**, not three datasets. Every mode ends up combining the other two as filters (e.g. *Egypt + Tomb + 3000–2000 BCE*).

### Properties of the data (the facts that drive the design)

1. **Heterogeneous.** A pyramid, a manuscript, a battle, a volcanic eruption and a dynasty share almost no attributes beyond name / place / time.
2. **Densely many-to-many.** The Great Pyramid is simultaneously in Egypt, Giza, Lower Egypt; Old Kingdom, 4th Dynasty; a pyramid (form), a tomb (function), a monument; linked to Khufu.
3. **Uncertain and contested.** Dates are ranges with fuzzy edges; some are disputed (Pompeii: August vs. October 79 CE; Thera eruption: ~1600 vs ~1500 BCE); attributions conflict (Great Sphinx: Khafre vs. Khufu); even modern-country assignment can be politically contested.
4. **Provenance-bearing.** Every important statement must remember *who said it, where, when retrieved, how sure*.
5. **Vocabulary-heavy.** Types, periods, cultures are hierarchical controlled vocabularies (tomb ⊃ passage tomb; Bronze Age ⊃ Late Bronze Age), and they differ by region.
6. **Growth path.** From ~50 items now to thousands (curated) and potentially millions (bulk imports from Wikidata, national registers, museum collections).

## 2. Recommendation

**PostgreSQL + PostGIS as the source of truth**, organised as a **relational knowledge graph**:

```
                ┌───────────────────────────── entity ─────────────────────────────┐
                │ one row per node: item, place, period, culture, polity, dynasty,  │
                │ person, concept, event, text, … ; attributes JSONB for long tail  │
                └───┬──────────────┬───────────────┬───────────────┬───────────────┘
                    │              │               │               │
             entity_name     location (GEO)  temporal_extent  relation (POV / graph)
             external_id     point/geometry   4-bound ranges   subject –predicate→ object
                    │              │               │               │
                    └──────────────┴──────┬────────┴───────────────┘
                                          │  every statement row → claim_id (NOT NULL)
                                        claim ── claim_evidence ── source
                                (confidence, rank, status)   (locator, URL, retrieved_at)
```

- **Structured tables** for what is stable across all kinds of knowledge: identity, names, external IDs, locations, temporal extents, typed relations, sources, claims.
- **`JSONB attributes`** for what varies by kind (a pyramid's base length, a manuscript's shelfmark, an eruption's VEI). New kinds of knowledge need **no schema migration**.
- **Generic `relation` table + a controlled `predicate` vocabulary** instead of one join table per relationship kind. Adding "depicts", "composed_by", "sung_at" later is a data change, not a schema change.
- **Claims layer**: every location, temporal extent, relation and name row points to a claim; a claim has ≥1 evidence rows pointing at sources. Conflicting claims coexist; a `rank` (preferred / normal / deprecated) chooses the *default display* without deleting the alternatives.

For the POC the same schema runs on **SQLite** (Python stdlib, no dependencies). The DDL avoids SQLite-only features; spatial filtering uses bounding boxes + haversine in the POC and maps 1-to-1 to PostGIS `ST_*` functions (shown side by side in [QUERY_EXAMPLES.md](QUERY_EXAMPLES.md)).

## 3. Alternatives considered

| Option | Strengths | Why not the source of truth |
|---|---|---|
| **Document DB** (MongoDB, Firestore) | Flexible per-item documents; easy to start | Many-to-many and shared vocabularies become duplicated strings or manual references; no referential integrity; claim-level provenance inside nested docs is awkward to query ("all claims from source X with low confidence"). Postgres JSONB gives the same flexibility where needed. |
| **Property-graph DB** (Neo4j, Memgraph) | Natural for relationships and traversal | Weaker at the other two axes: spatial indexing and interval-range filtering on millions of rows; smaller ops/hosting ecosystem; reification (edge-level provenance) is possible but clumsy. Our graph traversals are shallow (vocabulary hierarchy, part_of) and fit recursive CTEs. |
| **RDF triple store** (Blazegraph, GraphDB, Fuseki) + CIDOC-CRM | Maximum interoperability with cultural-heritage LOD (Wikidata, Pleiades, PeriodO, ARIADNE); standard provenance vocabularies | High modelling and operational cost; slow for map+timeline UI queries; hard for a small team. **We keep RDF compatibility as an export target** (stable IDs, external-ID crosswalk, predicate table mappable to CIDOC-CRM / Wikidata properties). |
| **Search engine** (Elasticsearch / OpenSearch / Meilisearch) | Full-text, faceting, geo & range filters, fast UI | Not a system of record (no transactions, no integrity). **Planned as a derived index** rebuilt from Postgres. |
| **Pure relational, one table per item type** | Strong typing | Every new kind of knowledge = new tables + migrations; the exact rigidity the project must avoid. |

**Conclusion:** relational core + JSONB + generic typed relations + claims. This is the approach Wikidata's own data model (statements with qualifiers, references and ranks) proves at scale, implemented on infrastructure that is excellent at geo and range queries.

## 4. Key design decisions (short rationale)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Everything is an `entity`** (items, places, periods, cultures, persons, concepts, events) | POV-First can pivot on *any* node: a person, a dynasty, a concept. Places and periods can themselves have locations, times and sources. Future layers (texts, religions, geology, music) are new `kind` values. |
| D2 | **Facets instead of one type field**: form (pyramid), function (tomb), item kind (structure) are separate relations | "Pyramid" and "tomb" are different axes; the Great Pyramid is both, a Mesoamerican pyramid is a temple platform, not a tomb. Flattening loses this. |
| D3 | **Time stored as numeric astronomical years with four bounds** (earliest/latest start, earliest/latest end) + precision + EDTF + original label | Allows correct overlap queries on fuzzy ranges, deep time (float64), and any display calendar. Display strings are *derived*, never the stored truth. |
| D4 | **Display calendars are formatters** (CE/BCE, BP, Hebrew AM, …) | The same instant can be rendered many ways; adding a calendar never touches data. |
| D5 | **Claims + evidence on every factual row** | Mandatory provenance; disagreement is preserved, not resolved. |
| D6 | **Geography = geometry + place graph** | Coordinates answer "near here"; the place hierarchy (and separate *historical* regions like Upper Egypt, Mesoamerica) answers "in Egypt". Both are needed; neither is derivable from the other reliably. |
| D7 | **External-ID crosswalk** (`external_id` table) | Idempotent re-import; deduplication across sources; linking back to Wikidata/Pleiades/UNESCO. |
| D8 | **Tags only for folksonomy** | Uncontrolled strings are allowed for UI/editorial convenience but never used as the backbone of queries. |

## 5. Scalability path

| Scale | Setup | Notes |
|---|---|---|
| POC (≤ 1k entities) | SQLite file, Python scripts | Current state. |
| Curated product (10k–100k) | PostgreSQL 16 + PostGIS; GiST on geometry; B-tree/GiST on time bounds (or `numrange`); GIN on JSONB and trigram names | A single modest server. API layer (e.g. FastAPI/PostgREST). |
| Bulk imports (1M–10M) | Same core + **derived OpenSearch index** (denormalised item documents with facet arrays, geo_point, time bounds) + **vector tiles** (Martin / pg_tileserv) for map rendering + precomputed **time buckets** (century / millennium histograms) for the timeline | Source-of-truth stays relational; indexes are rebuildable. Partition `claim`/`claim_evidence` by source if needed. Staging schema per import with raw snapshots. |
| LOD publishing | Periodic export as JSON-LD / Linked Art / CIDOC-CRM-aligned RDF, CSV dumps | Keeps interoperability without running a triple store as primary. |

Performance notes:
- TIME queries hit `(earliest_start, latest_end)` — index both; for Postgres use a generated `numrange(earliest_start, latest_end)` with GiST for `&&` overlap.
- POV queries expand the concept hierarchy first (small), then join `relation` on `(predicate, object_id)` — index that pair.
- GEO queries: PostGIS `ST_Intersects` / `ST_DWithin` on `geography(Point)`; place-hierarchy containment via a materialised closure table once the hierarchy is large.

## 6. Extensibility (what the core does *not* prevent)

| Future layer | How it fits without redesign |
|---|---|
| Historical events, battles | `entity.kind = 'event'` + location + temporal_extent + relations (`participant`, `occurred_at`, `depicted_in`) — already demonstrated (Battle of Kadesh, Vesuvius eruption). |
| Civilizations, religions, traditions | `kind = 'culture' / 'religion' / 'tradition'`, each with own time/space extents and `broader` hierarchy. |
| People | `kind = 'person'`; life/reign as temporal_extents with role; relations `commissioned_by`, `buried_in`, `ruled`. |
| Texts, manuscripts, artifacts | `kind = 'item'` with `item_kind` object/text; relations `found_at`, `held_by`, `copy_of`; attributes JSONB for shelfmarks, materials. |
| Geology, natural history, deep time | Float years to ±9×10¹⁵; `precision = 'ka' | 'Ma'`; `kind = 'event'` / `'geological_unit'`. |
| Scientific chronology | Multiple dating claims per entity (radiocarbon vs. historical) with method in claim attributes. |
| Multimedia, contextual audio/music | New `media` table (entity_id, media_type, uri, license, source_id, temporal/geo context) — additive table, no change to core. |
| Translations / Hebrew UI | `entity_name` with `lang` + `script`; calendar formatters. |

## 7. What is deliberately *not* decided yet
See **OPEN QUESTIONS FOR GEOCHRONOS SPEC** in [README.md](README.md).
