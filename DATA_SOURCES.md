# GeoChronos — Data Sources

> The full machine-readable catalog (80 sources, 22 attributes each; 3 institutional sources added and 7 rows updated in the 2026-10-01 night run) is in [data/source_catalog.csv](data/source_catalog.csv).
> This document explains how to read it, which sources matter first, and how ingestion should work.

## 1. How the catalog was built (and how far to trust it)

- **Verified on the web on 2026-10-01**: 12 sources (official licence/API pages read, or used live in the POC).
  - Examples: Wikidata, Wikipedia, Pleiades, PeriodO, GeoNames, OpenStreetMap, OpenHistoricalMap, Met Museum, Art Institute of Chicago, XRONOS, Macrostrat, Hebcal.
- **Partially verified**: 9 sources, where the page was read but lacked the licence or API details.
- **Not verified**: 56 sources, taken from prior knowledge. Every uncertain value in these rows is literally marked `needs_verification`. That applies especially to licences, rate limits and endpoints.
- **Blocked sites.** Several important sites returned **HTTP 403** to automated requests: UNESCO WHC, Europeana, Smithsonian, Historic England and the Smithsonian GVP. The POC did **not** try to get around those blocks. Where needed, access should be arranged through their official exports or APIs, or by contacting the provider.

Column meaning (CSV): `API_available` yes/no/partial; `recommended_priority` P1 (backbone) → P4 (reference only); `integration_status`: *integrated (POC)* / *crosswalk IDs only (POC)* / *planned* / *candidate* / *reference only*; `verification`: how the row was checked.

## 2. The source map at a glance

| Layer | Primary candidates | Role in GeoChronos |
|---|---|---|
| Identity & crosswalk hub | **Wikidata** (P1) | Stable IDs, coordinates, first-pass dates and classes, external IDs to everything else |
| Official heritage status | **UNESCO WHC** (P1), national registers (Historic England NHLE, Canmore, Ireland SMR, France POP/Mérimée, Italy ICCD/ArCo, Israel IAA survey, US NRHP, Australian Heritage Database) | Authoritative designations, boundaries, official names |
| Ancient places & names | **Pleiades** (P1), World Historical Gazetteer, iDAI.gazetteer, DARE, Getty TGN, Kima (Hebrew-script names) | Historical GEO hierarchy, names over time |
| Modern geography | GeoNames, Natural Earth, OpenStreetMap | Modern admin hierarchy, point-in-polygon continent/country assignment, footprints |
| Historical boundaries | OpenHistoricalMap (CC0), Seshat/Cliopatria | "Which polity controlled this place at time T" |
| Periods | **PeriodO** (P1), iDAI.chronontology | Region-specific period definitions, each with its authority |
| Concepts / facets | **Getty AAT** (P1), Library of Congress, GND | Form / function / material vocabularies, multilingual labels |
| Scientific dating | XRONOS, p3k14c | Radiocarbon claims attached to Items |
| Archaeological data | ARIADNE, Open Context, tDAR, DINAA, EAMENA, MAEASaM | Site/context/find-level data; coverage for Africa & MENA |
| Museums & objects | Met, Art Institute of Chicago, Smithsonian, Europeana, Cleveland, Rijksmuseum, Penn, Louvre, British Museum (reference) | Artefact Items, find spots, current keepers, images |
| People | Wikidata, Getty ULAN, VIAF, GND | Person entities and disambiguation |
| Texts | Sefaria, Perseus, Trismegistos, ToposText, Leon Levy DSS Library | Text Items; place↔text POV links; primary evidence (Josephus, Pliny) |
| Geology & natural history | Smithsonian GVP, NOAA NCEI hazards, Macrostrat, PBDB, Neotoma, GBIF | Geological events and deep-time context |
| Literature / citations | OpenAlex, Crossref | Resolving evidence to DOIs |
| Media & audio (future) | Wikimedia Commons, Europeana, British Library Sounds, Freesound, MusicBrainz, 3D repositories | Images, soundscapes, music tied to place & time |
| Calendar reference | Hebcal | Test fixtures for the Hebrew-calendar formatter |

## 3. Tier-1 sources in detail

### Wikidata — backbone, never the final word
- **Provides:** QIDs, labels/aliases in many languages, coordinates (P625), country (P17), admin area (P131), instance-of (P31), dates (P571/P580/P582/P585/P569/P570), and external IDs:
  - UNESCO P757, Pleiades P1584, GeoNames P1566, TGN P1667, OSM P402, Historic England P1216.
- **Access:**
  - SPARQL at `query.wikidata.org` (used by the POC with batched `VALUES` queries).
  - Weekly dumps.
  - Per-entity JSON.
  - The search API rate-limited the POC after about 10 rapid calls. Batch everything.
- **Licence:** CC0 (verified).
- **What the POC learned:**
  - **Dates come back in astronomical years.** WDQS returns BCE years in astronomical numbering and Gregorian-normalised. "1274 BCE" comes back as `-1273`, and Titus's Julian birthday comes back shifted to the Gregorian 28 Dec.
  - **Coarse precisions have ambiguous boundaries.** Century and millennium precision do not say where the unit starts. The importer widens those ranges by one unit and says so in the claim note.
  - **"Country" (P17) sometimes lists ancient states.** Persepolis lists the Achaemenid and Macedonian Empires; Masada lists Judaea. The importer classifies a P17 value as a historical polity when it has a dissolution date or no continent.
  - **Some links are wrong.**
    - Lalibela → "Eastern Orthodoxy"; Ethiopian Orthodoxy is Oriental Orthodox.
    - Angkor Wat inception "802"; it was built 1113–1150.
    - Dead Sea Scrolls "part of Judaism".
    - Monks Mound "named after Trappist Cistercian monk".

    These are imported as **disputed** claims or listed in a curation queue. They are never silently accepted or deleted.
  - **Some items have no English label.** Caral (Q219279) is one.

### UNESCO World Heritage List
- **Provides:** official property IDs, names, inscription criteria and year, and boundaries.
- **Access:** the site blocked automated requests (403). Official syndication and exports exist; their exact URL and terms are `needs_verification`.
- **Licence:** `needs_verification`. UNESCO website terms are not a blanket open licence, so confirm before redistributing any text or boundaries.
- **Use now:** property IDs via Wikidata P757 (count in `build/build_report.md`) and deep links to the property pages.

### Pleiades
- **Provides:** scholarly gazetteer of ancient places, names and time periods. Strong on the Mediterranean and Near East.
- **Access:** daily JSON, CSV and KML dumps, weekly RDF, and quarterly releases on GitHub and Zenodo (verified).
- **Licence:** CC BY 3.0 (verified). Requires attribution.
- **Use:** historical names and locations. The POC already holds Pleiades IDs obtained via Wikidata P1584.

### PeriodO
- **Provides:** a gazetteer of *scholarly period definitions*. Each period carries its authority, spatial coverage and start/end.
- **Access:** JSON, Turtle and CSV dataset dumps (verified).
- **Licence:** described as public domain (confirm the exact wording).
- **Why it matters:** GeoChronos needs exactly this. "Neolithic" or "Old Kingdom" has different dates in different sources and regions, and PeriodO stores each definition with its authority.

### Getty AAT
- **Provides:** hierarchical, multilingual concept vocabulary for forms (pyramid, dolmen, tholos), functions and materials.
- **Licence:** ODC-By (needs_verification). The POC could not read the Getty data-services page automatically.
- **Use:** align every `concept:form:*`, `concept:function:*` and `concept:material:*` entity to an AAT ID.

## 4. Licensing considerations (important before scaling)

1. **CC0 sources can be merged freely:** Wikidata, OpenHistoricalMap, Met, Art Institute of Chicago, and likely PeriodO and GND.
2. **Attribution (CC BY / ODC-By):** Pleiades, GeoNames, XRONOS, Macrostrat, Getty and Hebcal.
   - Keep `source` and `claim_evidence` rows. They are also the attribution register.
   - Generate an attribution page from the `source` table.
3. **Share-alike can spread to derived data:**
   - OpenStreetMap is **ODbL**.
   - Wikipedia text is **CC BY-SA**.
   - Recommendation:
     - Never copy Wikipedia text; cite by revision only, as the POC already does.
     - Keep any OSM-derived geometry in a separate, separately-licensed layer so the ODbL share-alike requirement does not apply to the whole database. See OPEN QUESTIONS.
4. **Some data can't be used commercially (NC):** David Rumsey maps, many 3D models, and some Seshat data. Decide early whether GeoChronos may ever be commercial. That decision determines whether NC sources are allowed at all.
5. **Restricted or sensitive data:**
   - Unpublished site locations (tDAR, DINAA, EAMENA) must not be exposed at full precision. The `location.precision` field and a future "sensitivity" flag support this.
   - Indigenous cultural heritage requires consent-based handling. Budj Bim is managed with the Gunditjmara Traditional Owners.

## 5. Recommended ingestion strategy

```
 raw snapshot ──► staging (per source, untouched) ──► mapping/normalisation ──► claims + evidence ──► curated view
 (data/raw/*.json)    (import schema)                  (IDs, calendars, units)    (never overwrite)     (preferred ranks)
```

1. **Snapshot first, always.** Store the untouched API response with its query and retrieval time, like `data/raw/wikidata_<date>.json`. Every imported value must trace back to a snapshot.
2. **Identity resolution by crosswalk, not by name.** Match on external IDs (QID, UNESCO, Pleiades, GeoNames) through the `external_id` table. Name matching only proposes candidates for human review; in the POC, an exact-label query for "Petra" returned 18 different Wikidata items with 3+ sitelinks.
3. **Import as claims.** Each imported fact becomes a claim with `recorded_by = import:<source>`, evidence carrying the source, locator and URL, a confidence level, and status `accepted`. Nothing overwrites an existing claim. Disagreements become competing claims in the same `dispute_group`.
4. **Corroborate.** When a new source asserts something that already exists, add evidence to the existing claim instead of duplicating it. The POC does this for curated-vs-Wikidata agreements, such as the Great Pyramid being commissioned by Khufu.
5. **Curation queue.** Anything that cannot be mapped goes to a review list (see `build/build_report.md`, "Wikidata links not imported"). The same applies to anything that looks wrong.
6. **Idempotent re-runs.** Claim IDs are content hashes (`sha1(entity|type|statement)`), so re-importing the same snapshot creates no duplicates.
7. **Staged rollout (proposed):**
   - **Stage A (backbone):** Wikidata for all UNESCO cultural properties plus Wikidata "archaeological site" instances, which is ~tens of thousands. Add PeriodO periods and AAT concepts for facets.
   - **Stage B (enrichment):**
     - Pleiades names and locations for the ancient Mediterranean.
     - UNESCO official records, once access and licence are clarified.
     - XRONOS radiocarbon claims.
     - Museum open-access objects: Met, AIC, Smithsonian.
   - **Stage C (national depth):** national registers, starting with those that have clear open licences and APIs (England, Ireland, France, Netherlands, US NRHP), plus Israel IAA for the Levant.
   - **Stage D (new layers):** geological events (GVP, NCEI), texts (Sefaria, Perseus), and media/audio (Commons, Europeana, Freesound).
8. **Sensitive data gate.** Before publishing any dataset's coordinates, check its terms for site-protection rules and reduce precision where needed.
