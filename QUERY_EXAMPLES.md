# GeoChronos — Query Examples

> **Status: updated 2026-10-01 night run.** The previous version (pre-night) is kept in `backups/2026-10-01_2213_pre-night/QUERY_EXAMPLES.md`.
> Results below come from the night run's builds:
> - **base** = `build/geochronos_base.sqlite` (57-Item regression seed)
> - **full** = `build/geochronos.sqlite` (95 Items)
>
> **Every SQL block tagged `-- test:` is executed by `tests/test_query_examples.py`** and must return exactly the same entity set as the matching function in [scripts/geoquery.py](scripts/geoquery.py). Blocks marked **NOT EXECUTED (PostGIS sketch)** were not run and are untested.

## 0. Shared rules (apply to every query)

- **Usable claim:** `rank <> 'deprecated' AND status <> 'rejected'`.
  - Disputed, alternative and needs_verification claims **are** used, but flagged (`uncertain`, `uncertain_only`, `status`).
  - Rejected claims stay in the database for audit. Example: Tiwanaku "1580 BC".
- **Years:** stored as astronomical (1 BCE = 0, 2500 BCE = −2499). Query windows are given in historical years and converted.
- **Default TIME semantics (POC assumption, reversible):** `mode='possible'`, `open_end='evidence'`. An unknown bound reaches only as far as the evidence goes. `open_end='unbounded'` and `mode='certain'` are explicit alternatives (§2).

---

## 1. GEO-First

### 1.1 Everything (transitively) in a place

```sql
-- test: geo_in_egypt
SELECT e.entity_id, e.canonical_name, g.depth, g.bases, g.uncertain_only
FROM v_geo_closure g JOIN entity e ON e.entity_id = g.entity_id
WHERE g.place_id = 'place:country:egypt' AND e.kind IN ('item')
ORDER BY e.canonical_name;
```

| profile | result |
|---|---|
| base | Abu Simbel, Great Pyramid, Great Sphinx, Karnak, Mask of Tutankhamun, Pyramid of Djoser, Rosetta Stone (find place), KV62 — 8 Items. Meroë (Sudan) is absent. |
| full | the same 8 (the expansion added no Items in Egypt) |

`bases` says *on what basis* an Item is in a place, for example `political (modern state, Wikidata P17)` or `historical/cultural region (curated)`.

Example: Taputapuātea reaches Europe only on a political basis (France). Rapa Nui reaches South America politically (Chile) and Oceania geographically. The data keeps both; choosing a display policy is a product decision (see SPEC_INPUTS.md).

Continent counts:

| profile | Europe | Asia | Africa |
|---|---|---|---|
| base | 16 | 15 | 12 |
| full | 22 | 31 | 18 |

### 1.2 Radius (effective point = own point, or inherited via `part_of` / `found_at`)

```sql
-- test: geo_near_giza_20km
SELECT e.entity_id, e.canonical_name, MIN(haversine_km(29.97915, 31.13422, p.lat, p.lon)) AS km,
       GROUP_CONCAT(DISTINCT p.via || ':' || p.point_entity_id) AS via, MAX(p.uncertain) AS uncertain
FROM v_entity_point p JOIN entity e ON e.entity_id = p.entity_id
WHERE e.kind IN ('item')
GROUP BY e.entity_id HAVING km <= 20 ORDER BY km;
```

Result in both profiles: Great Pyramid (0.0 km), Great Sphinx (0.55 km), Pyramid of Djoser (14.4 km).

- `via` names the source of the point: `own:<entity>`, or `found_at:<place>` (e.g. Rosetta Stone → Fort Julien and Rashid) or `part_of:<item>` (Tower of Jericho → Tell es-Sultan).
- `v_entity_point` never uses `reported_point` (an unverified object coordinate) or `gazetteer_point` (Pleiades, QA only).

```sql
-- NOT EXECUTED (PostGIS sketch, untested)
SELECT e.canonical_name, ST_Distance(l.geog, ST_MakePoint(31.13422, 29.97915)::geography)/1000 AS km
FROM location l JOIN claim c USING (claim_id) JOIN entity e USING (entity_id)
WHERE c.rank <> 'deprecated' AND c.status <> 'rejected' AND l.role IN ('primary','find_spot')
  AND ST_DWithin(l.geog, ST_MakePoint(31.13422, 29.97915)::geography, 20000);
```

---

## 2. TIME-First

Window: 2500 BCE ± 500, i.e. 3000–2000 BCE, which is astronomical −2999 … −1999.

### 2.1 Default: possible overlap, unknown bounds read "as far as the evidence goes"

```sql
-- test: time_2500_possible_evidence
SELECT DISTINCT e.entity_id, e.canonical_name
FROM temporal_extent t
JOIN claim c  ON c.claim_id = t.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
JOIN entity e ON e.entity_id = t.entity_id
WHERE t.role IN ('construction','creation','use','occupation','existence','event','deposition',
                 'destruction','reign','life','first_record')
  AND e.kind IN ('item')
  AND COALESCE(t.earliest_start, t.latest_start, t.earliest_end, t.latest_end) <= -1999
  AND COALESCE(t.latest_end, t.earliest_end, t.latest_start, t.earliest_start) >= -2999;
```

| profile | n | Items |
|---|---|---|
| base | 10 | Newgrange, Skara Brae, Stonehenge, Knossos, Great Pyramid, Pyramid of Djoser, Great Sphinx, Caral, Mohenjo-daro, Ziggurat of Ur |
| full | 15 | the 10 above + Tel Megiddo, Troy, Harappa, Babylon, Palmyra |

The 5 extra in full come from the **expansion** (new Items), not from a behaviour change. Palmyra matches only at the window's boundary: its "first mention, early 2nd millennium BCE" claim is read as 2000–1701 BCE.

Each result row carries three renderings of the same stored value (from `geoquery.time_overlap`):

| Item | civil | BP | Hebrew calendar |
|---|---|---|---|
| Newgrange | c. 3200–3000 BCE | c. 5,149–4,949 cal BP | c. AM 561–762 [computed proleptically] |
| Stonehenge | c. 3150–1500 BCE | c. 5,099–3,449 cal BP | c. AM 611–2,262 [computed proleptically] |

"[computed proleptically]" is new tonight. The fixed Hebrew calendar replaced the observational one gradually between 70 and 1178 CE (English Wikipedia, "Hebrew calendar", revision in `wikipedia_evidence.json`). Earlier AM values are back-calculated, not historical calendar dates.

### 2.2 Alternatives

```sql
-- test: time_2500_certain
SELECT DISTINCT e.entity_id, e.canonical_name
FROM temporal_extent t
JOIN claim c  ON c.claim_id = t.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
JOIN entity e ON e.entity_id = t.entity_id
WHERE t.role IN ('construction','creation','use','occupation','existence','event','deposition',
                 'destruction','reign','life','first_record')
  AND e.kind IN ('item')
  AND t.latest_start IS NOT NULL AND t.earliest_end IS NOT NULL AND t.latest_start <= t.earliest_end
  AND t.latest_start <= -1999 AND t.earliest_end >= -2999;
```

```sql
-- test: time_2500_possible_unbounded
SELECT DISTINCT e.entity_id, e.canonical_name
FROM temporal_extent t
JOIN claim c  ON c.claim_id = t.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
JOIN entity e ON e.entity_id = t.entity_id
WHERE t.role IN ('construction','creation','use','occupation','existence','event','deposition',
                 'destruction','reign','life','first_record')
  AND e.kind IN ('item')
  AND COALESCE(t.earliest_start, -1e18) <= -1999 AND COALESCE(t.latest_end, 1e18) >= -2999;
```

| mode | base | full | difference explained |
|---|---|---|---|
| possible / evidence (default) | 10 | 15 | — |
| certain | 10 | 15 | Same sets tonight. "Certain" now requires a known, non-empty [latest_start, earliest_end] (stricter than the pre-night rule). |
| possible / unbounded | 13 | 22 | Adds Items whose end (or start) is unknown, e.g. Göbekli Tepe ("to at least 8000 BCE"), Jericho, Budj Bim, and in full also Chicxulub ("slightly over 66 Ma", end unknown), Murujuga, Leptis Magna, Kuk Swamp. They are flagged `open_ended` / `open_start`. |

### 2.3 Unknown time is listed, not dropped

`geoquery.time_unknown()` returns Items with no usable dated activity (both profiles): **Ahu Tongariki**, **Qumran Caves**. A TIME view should show them as "date unknown", not omit them.

---

## 3. POV-First

```sql
-- test: pov_pyramid
SELECT e.entity_id, e.canonical_name,
       GROUP_CONCAT(DISTINCT r.predicate_id || ':' || o.canonical_name) AS via,
       MAX(CASE WHEN c.status IN ('disputed','needs_verification') THEN 1 ELSE 0 END) AS has_uncertain_link
FROM relation r
JOIN v_hierarchy h ON h.descendant_id = r.object_id AND h.ancestor_id = 'concept:form:pyramid'
JOIN claim c  ON c.claim_id = r.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
JOIN entity e ON e.entity_id = r.subject_id
JOIN entity o ON o.entity_id = r.object_id
WHERE r.predicate_id IN ('instance_of','has_form','has_function','made_of','culture','period',
                         'polity','dynasty','religion','theme')
  AND e.kind IN ('item')
GROUP BY e.entity_id ORDER BY e.canonical_name;
```

| query | result (base = full unless stated) |
|---|---|
| pyramids (form, incl. narrower) | Caral, El Castillo, Great Pyramid, Pyramid of Djoser, Pyramid of the Sun, Pyramids of Meroë. The Ziggurat and Monks Mound are not pyramids under this definition. |
| megalithic (form) | Carnac, Menga, Gochang, Göbekli Tepe, Nan Madol, Newgrange, Stonehenge, Ħaġar Qim |
| tombs (function) | 11 Items in both profiles |
| mosques (full) | Great Mosque of Djenné, Hagia Sophia (function carries its periods as qualifiers) |
| inscriptions & the Hebrew Bible (full) | Mesha Stele, Tel Dan stele, Siloam inscription |
| architectural style "Doric order" | Parthenon (new facet `has_style`, from Wikidata P149) |

---

## 4. Combined (GEO × TIME × POV)

```sql
-- test: combined_egypt_tomb_3000_2000
SELECT g.entity_id FROM v_geo_closure g JOIN entity e ON e.entity_id = g.entity_id
WHERE g.place_id = 'place:country:egypt' AND e.kind = 'item'
INTERSECT
SELECT r.subject_id FROM relation r
JOIN v_hierarchy h ON h.descendant_id = r.object_id AND h.ancestor_id = 'concept:function:tomb'
JOIN claim c ON c.claim_id = r.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
WHERE r.predicate_id IN ('instance_of','has_form','has_function','made_of','culture','period',
                         'polity','dynasty','religion','theme')
INTERSECT
SELECT t.entity_id FROM temporal_extent t
JOIN claim c ON c.claim_id = t.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
WHERE t.role IN ('construction','creation','use','occupation','existence','event','deposition',
                 'destruction','reign','life','first_record')
  AND COALESCE(t.earliest_start, t.latest_start, t.earliest_end, t.latest_end) <= -1999
  AND COALESCE(t.latest_end, t.earliest_end, t.latest_start, t.earliest_start) >= -2999;
```

| query | base | full |
|---|---|---|
| Egypt + Tomb + 3000–2000 BCE | Great Pyramid, Pyramid of Djoser | same |
| Megalithic + Europe + 5000–2000 BCE | Carnac, Menga, Newgrange, Stonehenge, Ħaġar Qim | same |
| Levant + text + 1000–500 BCE | — | Mesha Stele, Tel Dan stele, Siloam inscription |

---

## 5. Provenance ("why do we believe this?")

```sql
-- test: dispute_vesuvius
SELECT c.claim_id, c.rank, c.status, c.confidence, t.label,
       GROUP_CONCAT(ev.source_id || ' [' || COALESCE(ev.locator,'') || ']', '; ') AS evidence
FROM claim c
LEFT JOIN temporal_extent t ON t.claim_id = c.claim_id
LEFT JOIN claim_evidence ev ON ev.claim_id = c.claim_id
WHERE c.dispute_group = 'vesuvius-79:date'
GROUP BY c.claim_id ORDER BY c.rank DESC;
```

Wikidata evidence locators now name their snapshot (`Q37200#P625@2026-10-01T222038+0300`). A value asserted by two snapshots has two evidence rows on one claim. A value dropped by a later snapshot is kept, ranked `deprecated`, with a note.

---

## 6. Changes from the pre-night version of this document

| change | type | impact |
|---|---|---|
| Rejected claims excluded in GEO views and hierarchy, not only in TIME/POV | behaviour fix | no change on current data; covered by `tests/test_claim_filters.py` |
| Unknown **start** now handled like unknown end ("evidence"); `unbounded` covers both | behaviour change | no change in the base results; documented in §2 |
| `certain` mode requires a known, non-empty [latest_start, earliest_end] | behaviour change | same sets tonight |
| `life`, `reign`, `first_record` count as dated activity | behaviour fix | Lucy no longer listed as "date unknown"; Babylon and Palmyra first records match |
| Wikidata decade/century/millennium values interpreted per calibration (no ±1-unit widening) | data fix | Wikidata-derived extents narrowed; base results unchanged |
| GEO result columns `bases`, `uncertain_only`, `via:<entity>` | addition | — |
