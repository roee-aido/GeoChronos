# GeoChronos — Data Model

> Physical schema: [db/schema.sql](db/schema.sql) · Architecture rationale: [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md)
>
> **Updated 2026-10-01 (night run)** to match the implementation. The pre-night version is in `backups/2026-10-01_2213_pre-night/DATA_MODEL.md`. The changes are summarised in §9.

## 1. Core idea

Everything GeoChronos knows is a **statement about an entity**, and every statement is a **claim with evidence**.

```
entity ──< entity_name      (identity: names in many languages)
       ──< external_id      (crosswalk: Wikidata, UNESCO, Pleiades, …)
       ──< location         (GEO: points / geometries)
       ──< temporal_extent  (TIME: uncertain intervals)
       ──< relation >── entity   (POV & graph: typed links to any other entity)
                 │
   every row above ─► claim ──< claim_evidence >── source
                      (rank, status, confidence, dispute_group, note)
```

The three exploration modes are three entry points into the same tables:

| Mode | Starts from | Walks |
|---|---|---|
| GEO-First | `location` (coordinates) or a place entity | `v_geo_closure` → entities → their time & POV |
| TIME-First | an interval | `temporal_extent` overlap → entities → their place & POV |
| POV-First | any entity: concept, culture, period, person, religion, event | `relation` (+ `v_hierarchy` for narrower concepts) → entities → place & time |

## 2. Entities

### 2.1 `entity` — every node

| Field | Type | Notes |
|---|---|---|
| `entity_id` | text PK | Stable, human-readable slug with a kind prefix: `item:great-pyramid-of-giza`, `culture:ancient-egypt`. Never reused. (A UUID can be added as a secondary key at scale.) |
| `kind` | text | Open vocabulary: `item`, `place`, `period`, `culture`, `polity`, `dynasty`, `person`, `concept`, `event`, `religion`, `organization`. Future kinds (`text`, `tradition`, `geological_unit`, `media`) need no migration. |
| `canonical_name` | text | Default display name. Other names live in `entity_name`. |
| `description` | text | Short neutral description. |
| `attributes` | JSON(B) | The long tail. For example: `place_type`, `scheme`, Wikidata `instance_of` labels, heritage designations, future pyramid base length or manuscript shelfmark. It is **materialised** from preferred attribute claims, so the flexible fields also keep provenance. |
| `record_status` | text | `active` / `draft` / `merged` / `withdrawn`. Merging keeps the old ID resolvable. |

**Which concepts deserve their own entity (vs. a tag)?** Anything that has its own place, time, sources, hierarchy or disagreement gets an entity:

| Kind | Examples in seed | Why structured |
|---|---|---|
| `item` | Great Pyramid, Rosetta Stone, Tower of Jericho | The things being explored: sites, structures, monuments, settlements, tombs, caves, landscapes, objects, texts. |
| `place` | Egypt, Upper Egypt, Mesoamerica, Anatolia, London | Hierarchies, historical vs modern regions, own geometry. |
| `period` | Old Kingdom, PPNA, Second Temple period | Own time extents that **differ by authority and region**. |
| `culture` | Ancient Egyptian, Maya, Gravettian | Own spatial and temporal extent; many-to-many with items. |
| `polity` / `dynasty` | Achaemenid Empire, Fourth Dynasty | Own time extents; competing chronologies. |
| `person` | Khufu, Herod, Rædwald | Life/reign extents; roles (commissioned, buried, attributed). |
| `religion` | Judaism, Ethiopian Orthodox Tewahedo | Hierarchy (Oriental Orthodoxy ⊂ Christianity). |
| `event` | Battle of Kadesh, Minoan eruption, Vesuvius 79 | Dated occurrences, including battles and geological events. |
| `concept` | pyramid, tomb, limestone, Seven Wonders | Controlled vocabularies with `broader` hierarchy, organised in **schemes**. |
| `organization` | British Museum, Israel Museum | Current keepers of objects. |

**Concept schemes (facets), deliberately kept separate:**

| Scheme | Predicate | Examples | Note |
|---|---|---|---|
| `item_type` | `instance_of` | archaeological site, city, monument, cave, artefact, text | What kind of thing it is at the top level. |
| `form` | `has_form` | pyramid ⊃ step pyramid, Nubian pyramid, Mesoamerican pyramid; megalith ⊃ dolmen, passage tomb, stone circle | Physical/architectural shape. |
| `function` | `has_function` | funerary ⊃ tomb; religious ⊃ temple ⊃ church | Purpose. **Form ≠ function**: Great Pyramid = pyramid + tomb; Pyramid of the Sun = pyramid + temple. |
| `material` | `made_of` | limestone, granite, gold | Mostly imported from Wikidata P186. |
| `theme` | `theme` | Seven Wonders, archaeoastronomy, early urbanism | Topical points of view. |

Umbrella concepts capture fuzzy categories without distorting the strict ones. `pyramidal structure` ⊃ pyramid, ziggurat and platform mound. "Show pyramids" therefore excludes the Ziggurat of Ur, while "Show pyramidal structures" includes it.

**Tags (`entity_tag`)** are only for uncontrolled editorial labels. They are never used as the backbone of queries.

### 2.2 `entity_name`

| Field | Notes |
|---|---|
| `name`, `lang` (BCP-47), `name_type` | `canonical` / `alternative` / `historical` / `native` / `abbreviation`. Examples: "Pyramid of Cheops" (historical), "מצדה" (he, native), "KV62" (abbreviation). |
| `claim_id` | Names are claims too: who calls it what, according to whom. |

### 2.3 `external_id`

`(entity_id, authority, value, url, source_id)` stores crosswalks. Current authorities are `wikidata`, `unesco_whc`, `pleiades`, `getty_tgn`, `geonames`, `osm_relation` and `historic_england_nhle`. This table is the key to deduplication and idempotent re-import.

## 3. GEO representation

1. **Geometry (`location`)** holds a WGS84 point, an optional `geometry_wkt` (polygon/multipoint) and an optional bounding box, plus:
   - **`role`:**
     - `primary` for immovable sites.
     - `find_spot` for movable objects, **only if verified**: the object's P625 must lie within 5 km of the coordinates of its Wikidata P189 location of discovery.
     - `reported_point` for an object coordinate that could not be verified. It is stored but never used as a map point.
     - `gazetteer_point` for a Pleiades representative point, used for QA and corroboration only.
     - `current_location`, `extent` and `centroid` are available for later use.
   - **`precision`:** `exact` / `approximate` / `centroid` / `region` / `unknown`. This also supports deliberately generalised sensitive sites.
2. **Place graph (`relation`):**
   - `item —located_in→ place`, `place —part_of→ place`, `item —part_of→ item` (sub-structures), `object —found_at→ item/place`, `event —occurred_at→ place`.
   - **Modern hierarchy** (country, admin area) is imported from Wikidata P17/P131, and countries are linked to continents through P30.
   - **Historical/cultural regions** (Upper Egypt, Nubia, Levant, Mesoamerica, Anatolia) are curated `place` entities.
3. **Transcontinental countries use `overlaps`, not `part_of`.** Turkey overlaps Europe and Asia, so Göbekli Tepe reaches **Asia** only, through Anatolia.
4. **Current keeper ≠ location.**
   - `held_by` (Rosetta Stone → British Museum → London) is **not** geographic containment.
   - "What was found in Egypt" and "what is in London today" are different questions, and both are answerable.
5. **Inheritance.** `v_entity_point` gives any entity without coordinates the point of what it is `part_of` or `found_at`. The Tower of Jericho inherits Tell es-Sultan's point, and Tutankhamun's mask inherits KV62's.

## 4. TIME representation

### 4.1 Stored value (never a display string)

| Field | Meaning |
|---|---|
| `role` | What the interval describes: `construction`, `creation`, `use`, `occupation`, `existence`, `event`, `deposition`, `destruction`, `reign`, `life`, `discovery`, `restoration`, `relocation`, `reuse`, `damage`, … An item has **many** extents. |
| `earliest_start`, `latest_start`, `earliest_end`, `latest_end` | **Astronomical years**, inclusive (1 BCE = 0, 2500 BCE = −2499). Four bounds capture fuzzy edges independently. Karnak, for example: start within Senusret I's reign (1971–1926 BCE), end somewhere in the Ptolemaic period (305–30 BCE). `NULL` = open/unknown. Stored as float64, which is exact up to ±9×10¹⁵ years, so deep time works (Blombos Cave ≈ 101,000 years ago; the Middle Stone Age from ≈ 280,000 years ago). |
| `precision` | `day` … `century`, `millennium`, `ka`, `Ma`. |
| `qualifier` | `circa`, `before`, `after`, `between`, `exact`. |
| `jdn_start`, `jdn_end` | Julian Day Numbers when day precision is known. Examples: the Rosetta decree, 27 March 196 BC (proleptic Julian); Lascaux's discovery, 12 Sep 1940; the Vesuvius candidate dates. |
| `source_calendar` | Calendar of the source value (`julian`, `gregorian`, `unspecified`, …). Needed to convert correctly. |
| `edtf` | ISO 8601-2 (EDTF) rendering for interchange. |
| `label` | The dating **as the source expressed it** ("between 2700 and 2500 BC"). |
| `dating_method` | historical, radiocarbon, dendrochronology, luminescence, numismatic, … |

**Authoring vs storage.** Seed authors write historical years (negative = BCE, no year 0), `±` uncertainties, `ka` values or ISO-like dates. `build_db.py` converts them to the stored form, so authors never do astronomical arithmetic by hand.

### 4.2 Query semantics

- **Possible overlap (default):** `earliest_start ≤ qEnd AND latest_end ≥ qStart`. It *could* have existed then.
- **Certain overlap:** `latest_start` and `earliest_end` must both be known, with `latest_start ≤ earliest_end`, `latest_start ≤ qEnd` and `earliest_end ≥ qStart`. It *must* have existed then.
- **Unknown bounds:**
  - Default `open_end='evidence'`: an unknown start or end reaches only as far as the attested bounds.
  - `open_end='unbounded'`: unknown bounds are read as −∞/+∞ (opt-in).
  - Both are POC working choices, not product decisions.
- **Default roles:** "active" roles (construction, use, occupation, event, …). Heritage-history roles (discovery, restoration, relocation) form a separate layer and are queried explicitly.
- **Competing claims:** every non-deprecated claim can match. Results report the best-ranked matching claim, how many claims matched, and whether the extent is open-ended.

### 4.3 Display representations (derived, never stored)

`scripts/timefmt.py` renders the same stored value as:

| Representation | Example (Great Pyramid, preferred claim) |
|---|---|
| Civil CE/BCE | `2700–2500 BCE` |
| Years before present | `4,649–4,449 cal BP` |
| Hebrew calendar (Anno Mundi) | `AM 1,061–1,262 [computed proleptically]`; day-precise dates render in full, e.g. the Rosetta decree as a Hebrew day/month/year. Dates before 1178 CE carry the 'computed proleptically' note: the fixed calendar replaced the observational one gradually between 70 and 1178 CE. |
| Hebrew numerals | `א׳ס״א–א׳רס״ב` (gematria with thousands) for a Hebrew UI |

**Rules:**
- **Year-level mapping:** a civil year Y overlaps AM Y+3760 and Y+3761, because the Hebrew year begins at Tishrei in autumn.
- **Day-level conversion:** full conversion via the Reingold–Dershowitz algorithms, self-tested against known anchor dates.
- **Before AM 1** (autumn 3761 BCE), the formatter says so explicitly instead of inventing negative AM years. This is a product decision; see OPEN QUESTIONS.
- **Other chronologies:** regnal dates (e.g. Kadesh = "Year 5 III Shemu day 9 of Ramesses II") are kept in `label`. Their absolute conversions under different chronologies are separate claims.

## 5. POV / relationships

`relation(subject_id, predicate_id, object_id, qualifiers JSON, claim_id)` stores all typed links. `predicate` is a controlled table: label, inverse, category, and the nearest Wikidata property and CIDOC-CRM property for linked-data export.

| Category | Predicates |
|---|---|
| geo | `located_in`, `overlaps`, `found_at`, `held_by`, `occurred_at`, `applies_to` |
| structural | `part_of`, `broader` |
| classification | `instance_of`, `has_form`, `has_function`, `made_of`, `culture`, `polity`, `dynasty`, `religion`, `theme` |
| time | `period` (membership in a named period is a classification, not a date) |
| association | `commissioned_by`, `attributed_to`, `burial_of`, `depicts`, `destroyed_by`, `participant`, `ruled`, `member_of` |

New relationship kinds (e.g. `mentions`, `composed_at`, `sung_during`) are **data**: insert a predicate row.

## 6. Provenance & evidence model

### 6.1 `claim`

| Field | Values / meaning |
|---|---|
| `statement_type` | `name`, `location`, `temporal`, `relation`, `attribute` |
| `rank` | `preferred` (default display) / `normal` / `deprecated` (kept for history, hidden by default). Wikidata-style. |
| `status` | `accepted`, `alternative` (a legitimate competing view), `disputed` (active disagreement), `needs_verification`, `rejected` |
| `confidence` + `confidence_score` | `high` / `medium` / `low` / `unknown`, with an optional 0–1 score |
| `dispute_group` | Claims competing for the same fact share a key: `sphinx:attribution`, `vesuvius-79:date`, `thera:date`, `masada:fall` |
| `note` | Interpretation or caveat in plain language |
| `recorded_by`, `recorded_at` | Who entered it (`curator:geochronos-poc`, `import:wikidata`) and when |
| `property`, `value` | For attribute claims (JSON value): the provenance-bearing part of the JSONB long tail |

### 6.2 `claim_evidence` and `source`

- **Evidence row:** `(claim_id, source_id, locator, url, retrieved_at, note)`. A claim can have several (corroboration).
- **`source` row:** title, type, publisher/institution, URL, **licence**, citation and reliability note.

**Rules enforced by the build:**
1. Every claim has ≥ 1 evidence row.
2. **Dates and coordinates may not rest on editorial curation alone.** They need a real source (Wikidata, Wikipedia revision, publication).
3. Classification decisions made by the curator (e.g. "Great Pyramid has_form pyramid") cite the description they were based on and are labelled "Curatorial classification…".
4. Disagreement is never resolved by deletion. Preference is expressed only through `rank`.

### 6.3 Examples of preserved disagreement in the seed

| Topic | Claims kept |
|---|---|
| Great Sphinx: who commissioned it | Khafre *(disputed)* · Khufu *(disputed)*; neither preferred |
| Eruption of Vesuvius: day | 24 Aug 79 (manuscript tradition) · after 17 Oct 79 (2018 graffito) · 24 Oct–1 Nov 79 (2022 study) · 24–25 Oct 79 (same study as summarised elsewhere) |
| Thera / Akrotiri destruction | c. 1600 BC or 1620–1530 BC (radiocarbon) · 1570–1480 BC (archaeological) |
| Great Pyramid construction | 2700–2500 BC (consensus range) · 2871–2604 BC (mortar radiocarbon) · 2620–2484 BC (reanalysis) · 2560 BCE (Wikidata) |
| Masada falls to Rome | 73 CE · 74 CE |
| Third Dynasty of Egypt | Shaw 2686–2613 · Baines & Malek 2650–2575 · Dodson & Hilton 2584–2520 |
| Abu Simbel | c. 1264–1244 BC · completed c. 1265 BC (same source, internally inconsistent) |
| Lalibela religion | Ethiopian Orthodox Tewahedo (curated) · Eastern Orthodoxy (Wikidata, *disputed*) |
| Angkor Wat inception | 1113–1150 (curated) · 802 (Wikidata, *disputed* with curator note) |

## 7. Example records

### 7.1 Authoring form (seed JSON; abridged from `data/seed/items.json`)

```json
{"id": "item:great-sphinx-of-giza", "name": "Great Sphinx of Giza", "ev": ["wp:Great Sphinx of Giza"],
 "pov": {"item_type": ["concept:type:monument"], "form": ["concept:form:colossal-statue"],
         "culture": ["culture:ancient-egypt"], "period": ["period:egypt-old-kingdom"], "dynasty": ["dynasty:egypt-4"]},
 "geo": {"located_in": ["place:locality:giza-necropolis"]},
 "links": [
   {"pred": "attributed_to", "obj": "person:khafre", "conf": "medium", "status": "disputed", "group": "sphinx:attribution"},
   {"pred": "attributed_to", "obj": "person:khufu",  "conf": "medium", "status": "disputed", "group": "sphinx:attribution"}],
 "time": [{"role": "creation", "from": -2600, "to": -2500, "qualifier": "between", "precision": "century",
           "label": "between 2600 and 2500 BC", "conf": "medium", "status": "accepted", "rank": "preferred"}]}
```

Coordinates, country, admin area, English aliases, Wikidata dates and external IDs are **not** authored. They are imported from the raw Wikidata snapshot as separate claims.

### 7.2 Stored form (rows after `build_db.py`, abridged)

```text
entity          item:great-sphinx-of-giza | item | Great Sphinx of Giza | {"wikidata_instance_of": [...]}
external_id     wikidata Q130958 · pleiades 536839380 · geonames 362903 · getty_tgn 7001337
location        lat 29.97527, lon 31.13768, role primary, precision approximate  → claim(evidence: wd:Q130958#P625)
temporal_extent role creation, earliest_start -2599, latest_start -2599, earliest_end -2499, latest_end -2499,
                precision century, qualifier between, label "between 2600 and 2500 BC"
                → claim(rank preferred, status accepted, evidence: Wikipedia rev 1377623009)
temporal_extent role construction, bounds -2599…-2500 (Wikidata P571 '-2559' at century precision = 26th century BCE, per the 2026-10-01 calibration)
                → claim(rank normal, evidence: wd:Q130958#P571)
relation        attributed_to → person:khafre   claim(status disputed, group sphinx:attribution)
relation        attributed_to → person:khufu    claim(status disputed, group sphinx:attribution)
relation        located_in → place:locality:giza-necropolis (curated; Wikidata's P276 points to a different item, so it went to the curation queue)
relation        located_in → place:country:egypt  (Wikidata P17)
```

### 7.3 A person, an event and a period use the same tables

```text
person:khufu            temporal_extent role reign  "26th century BC" (preferred) · "c. 2590–2566 BC" (alternative)
                        temporal_extent role life   (Wikidata P569/P570)
event:battle-of-kadesh  temporal_extent role event  "May 1274 BCE (low chronology)" (preferred) · "~20 years earlier (high)" (alternative)
                        relation participant → polity:hittite-empire, person:ramesses-ii; occurred_at → place:locality:kadesh
period:second-temple    temporal_extent role existence -515 … 70 (astronomical) · applies_to → place:region:levant
```

## 8. Extensibility checklist

| Future need | Change required |
|---|---|
| New item category (manuscript, battle site, shipwreck) | none. New concept rows. |
| New relationship type | one `predicate` row |
| New attribute for some items | attribute claims (materialised into `attributes` JSONB) |
| New calendar / era display | a formatter function, no data change |
| Geological events, deep time | `kind='event'`, `precision='ka'/'Ma'`, existing bounds |
| Multimedia & audio | additive `media` table `(media_id, entity_id, media_type, uri, licence, source_id, claim_id)`, optionally with its own temporal/geo context |
| Multilingual UI (Hebrew) | `entity_name` rows with `lang='he'`; Hebrew calendar formatter already present |
| Sensitive locations | `location.precision` + future `sensitivity` flag and generalised geometry |
| User contributions / moderation | new claims with `recorded_by='user:…'`, status `needs_verification`, plus a review workflow |


## 9. Night-run changes (2026-10-01) — implementation details

| Area | What is now implemented | Where |
|---|---|---|
| Claim filtering | All views (`v_hierarchy`, `v_geo_closure`, `v_entity_point`) exclude `rank='deprecated'` **and** `status='rejected'`. Disputed, alternative and needs_verification claims are kept and flagged (`uncertain`, `uncertain_only`). | db/schema.sql |
| GEO basis | `v_geo_closure.bases` = basis of the first edge: `political (modern state, Wikidata P17)`, `administrative (Wikidata P131)`, `historical/cultural region (curated)`. Lets a UI separate political from geographic placement (Rapa Nui, Taputapuātea) without choosing a policy. | build_db.py, schema |
| Inheritance reason | `v_entity_point` exposes `via`, `point_entity_id`, `location_claim_id` and `via_claim_id`, so a shown point always says why and on what evidence. | schema |
| Time bounds | Two more CHECKs: `earliest_start ≤ earliest_end` and `latest_start ≤ latest_end`. | schema |
| `time_basis` | `calendar` / `bp_1950` (source says BP) / `years_before_source` (source says "years ago"; stored relative to 1950 as an explicit POC assumption). The BP formatter does not label the last as BP. | schema, timefmt.py |
| Wikidata dates | WDQS returns year/month/day values in astronomical numbering (Gregorian-normalised days), but decade/century/millennium values as the historical year, unshifted. Calibrated against Special:EntityData JSON (raw files in `data/raw/wikidata_entitydata_2026-10-01/`). Intervals follow Wikidata Help:Dates, without extra widening. | build_db.wd_value_bounds, tests/test_calendars.py |
| Snapshots & supersession | All staged snapshots are processed oldest first. Evidence locators carry the snapshot id (`Q…#P625@<snapshot>`). The same value re-asserted adds an evidence row; a value missing from the latest snapshot is kept as `deprecated`, with a note (unless other sources support it). | build_db.py |
| Confidence | No automatic `high` for imported claims (build error if it happens). Curated `high` is used only where the cited source states it plainly. | build_db.checks |
| Attribute claims | `attrs` in the seed become attribute claims (with evidence) and are materialised into `entity.attributes`. Examples: Great Pyramid `original_height_m`, Rosetta `museum_number`. | build_db.py |
| External IDs | `external_id.source_id` = `src:wikidata` for IDs read from Wikidata, `src:gc-editorial` for curator-resolved QIDs (resolution method in `wikidata_targets*.json`). | build_db.insert_entities |
| Names | Hebrew labels, aliases and hewiki titles come from Wikidata; historical names come from Pleiades (with language codes). AI-supplied names are stored as `needs_verification` and noted as AI translations. Curator reviews can reject a bad imported name (e.g. Caral's Hebrew label 'שלום'). | build_db.py |
| New facets | `has_style` (Wikidata P149 architectural style) and `named_after` (P138). Time-scoped facet values use relation `qualifiers` (Hagia Sophia functions with periods). | vocabulary.json |
| Literature | `data/seed/literature.json` holds institutional pages and papers with an explicit `access_note` (e.g. "ABSTRACT ONLY (via OpenAlex)"). Evidence tokens look like `lit:<key>#abstract`. | seed |
