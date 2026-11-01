-- =====================================================================
-- GeoChronos — core schema v0.1
-- Target: PostgreSQL 16 + PostGIS.  POC runtime: SQLite 3 (Python stdlib).
--
-- Portability notes (SQLite -> PostgreSQL):
--   TEXT holding JSON        -> JSONB           (+ GIN index)
--   REAL                     -> DOUBLE PRECISION
--   geometry_wkt TEXT        -> geometry(Geometry, 4326)  (+ GiST index)
--   lat/lon pair             -> generated geography(Point) column
--   time bounds              -> + generated numrange(earliest_start, latest_end) (+ GiST, && operator)
--   TEXT timestamps (ISO)    -> TIMESTAMPTZ
-- No SQLite-only features are used except PRAGMA foreign_keys.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- SOURCES — where knowledge comes from (databases, publications, pages)
-- ---------------------------------------------------------------------
CREATE TABLE source (
    source_id        TEXT PRIMARY KEY,            -- e.g. 'src:wikidata'
    title            TEXT NOT NULL,
    source_type      TEXT NOT NULL CHECK (source_type IN
                        ('database','dataset','web_page','publication','museum_record',
                         'heritage_register','editorial','other')),
    publisher        TEXT,                        -- organisation / institution
    url              TEXT,
    license          TEXT,                        -- licence of the source data, 'unknown' if unverified
    citation         TEXT,                        -- human-readable citation
    reliability_note TEXT,
    attributes       TEXT NOT NULL DEFAULT '{}'   -- JSON: authors, year, doi, …
);

-- ---------------------------------------------------------------------
-- ENTITY — every node of the knowledge graph
-- kind: item | place | period | culture | polity | dynasty | person |
--       concept | event | religion | organization | … (open vocabulary)
-- ---------------------------------------------------------------------
CREATE TABLE entity (
    entity_id       TEXT PRIMARY KEY,             -- stable slug, e.g. 'item:great-pyramid-of-giza'
    kind            TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,                -- default display name (English in POC)
    description     TEXT,
    attributes      TEXT NOT NULL DEFAULT '{}',   -- JSON long tail; materialised from preferred attribute claims + editorial metadata
    record_status   TEXT NOT NULL DEFAULT 'active' CHECK (record_status IN ('active','draft','merged','withdrawn')),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX ix_entity_kind ON entity(kind);

-- ---------------------------------------------------------------------
-- CLAIM — one assertion about one subject entity. Every factual row in
-- entity_name / location / temporal_extent / relation points to a claim.
-- Competing claims about the same fact share a dispute_group.
-- ---------------------------------------------------------------------
CREATE TABLE claim (
    claim_id          TEXT PRIMARY KEY,
    entity_id         TEXT NOT NULL REFERENCES entity(entity_id),   -- subject
    statement_type    TEXT NOT NULL CHECK (statement_type IN
                        ('name','location','temporal','relation','attribute')),
    property          TEXT,                       -- attribute claims: key, e.g. 'original_height_m'
    value             TEXT,                       -- attribute claims: JSON value
    rank              TEXT NOT NULL DEFAULT 'normal' CHECK (rank IN ('preferred','normal','deprecated')),
    status            TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN
                        ('accepted','alternative','disputed','needs_verification','rejected')),
    confidence        TEXT NOT NULL DEFAULT 'unknown' CHECK (confidence IN ('high','medium','low','unknown')),
    confidence_score  REAL CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    dispute_group     TEXT,                       -- e.g. 'pompeii:destruction-date'
    note              TEXT,                       -- interpretation / caveat
    recorded_by       TEXT NOT NULL,              -- 'import:wikidata' | 'curator:geochronos-poc'
    recorded_at       TEXT NOT NULL
);
CREATE INDEX ix_claim_entity ON claim(entity_id);
CREATE INDEX ix_claim_dispute ON claim(dispute_group);

-- Evidence: a claim may be supported by several sources.
CREATE TABLE claim_evidence (
    evidence_id   INTEGER PRIMARY KEY,
    claim_id      TEXT NOT NULL REFERENCES claim(claim_id),
    source_id     TEXT NOT NULL REFERENCES source(source_id),
    locator       TEXT,                           -- record id, QID#property, page, section
    url           TEXT,                           -- direct link to the evidence
    retrieved_at  TEXT,                           -- ISO date the evidence was accessed
    note          TEXT
);
CREATE INDEX ix_evidence_claim ON claim_evidence(claim_id);
CREATE INDEX ix_evidence_source ON claim_evidence(source_id);

-- ---------------------------------------------------------------------
-- IDENTITY
-- ---------------------------------------------------------------------
CREATE TABLE entity_name (
    name_id     INTEGER PRIMARY KEY,
    entity_id   TEXT NOT NULL REFERENCES entity(entity_id),
    name        TEXT NOT NULL,
    lang        TEXT,                              -- BCP-47: 'en', 'he', 'ar', 'egy-Latn' …
    name_type   TEXT NOT NULL CHECK (name_type IN
                  ('canonical','alternative','historical','native','abbreviation')),
    claim_id    TEXT NOT NULL REFERENCES claim(claim_id)
);
CREATE INDEX ix_name_entity ON entity_name(entity_id);
CREATE INDEX ix_name_name ON entity_name(name);

-- Crosswalk to external authorities (Wikidata, UNESCO, Pleiades, PeriodO, …).
CREATE TABLE external_id (
    entity_id   TEXT NOT NULL REFERENCES entity(entity_id),
    authority   TEXT NOT NULL,                    -- 'wikidata' | 'unesco_whc' | 'pleiades' | …
    value       TEXT NOT NULL,
    url         TEXT,
    source_id   TEXT REFERENCES source(source_id),-- where the mapping was obtained
    PRIMARY KEY (entity_id, authority, value)
);
CREATE INDEX ix_extid_value ON external_id(authority, value);

-- ---------------------------------------------------------------------
-- GEO
-- role: primary (immovable site) | find_spot (verified against the find place) |
--       reported_point (point given by a source for a movable object, NOT verified as find spot) |
--       gazetteer_point (representative point from a gazetteer, e.g. Pleiades; QA/corroboration only) |
--       current_location | extent | centroid
-- ---------------------------------------------------------------------
CREATE TABLE location (
    location_id   INTEGER PRIMARY KEY,
    entity_id     TEXT NOT NULL REFERENCES entity(entity_id),
    role          TEXT NOT NULL DEFAULT 'primary',
    lat           REAL CHECK (lat IS NULL OR lat BETWEEN -90 AND 90),     -- WGS84
    lon           REAL CHECK (lon IS NULL OR lon BETWEEN -180 AND 180),
    geometry_wkt  TEXT,                           -- optional polygon / multipoint (PostGIS geometry)
    bbox_south REAL, bbox_west REAL, bbox_north REAL, bbox_east REAL,     -- optional bounding region
    precision     TEXT NOT NULL DEFAULT 'unknown' CHECK (precision IN
                    ('exact','approximate','centroid','region','unknown')),
    claim_id      TEXT NOT NULL REFERENCES claim(claim_id)
);
CREATE INDEX ix_location_entity ON location(entity_id);
CREATE INDEX ix_location_latlon ON location(lat, lon);

-- ---------------------------------------------------------------------
-- TIME — underlying value, never a display string.
-- Bounds are ASTRONOMICAL YEARS, inclusive (1 BCE = 0, 2500 BCE = -2499).
-- A year-precision bound covers the whole year. NULL bound = open/unknown.
-- Deep time: float64 is exact for integers up to ±9e15.
-- role: creation | construction | use | occupation | existence | event |
--       life | reign | discovery | destruction | deposition | excavation | …
-- ---------------------------------------------------------------------
CREATE TABLE temporal_extent (
    extent_id       INTEGER PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entity(entity_id),
    role            TEXT NOT NULL,
    earliest_start  REAL,
    latest_start    REAL,
    earliest_end    REAL,
    latest_end      REAL,
    precision       TEXT NOT NULL CHECK (precision IN
                      ('day','month','year','decade','century','millennium','ka','Ma')),
    qualifier       TEXT CHECK (qualifier IS NULL OR qualifier IN ('exact','circa','before','after','between')),
    edtf            TEXT,                         -- Extended Date/Time Format (ISO 8601-2), e.g. '-2559~/-2539~'
    label           TEXT,                         -- the dating as expressed by the source
    source_calendar TEXT NOT NULL DEFAULT 'unspecified',  -- gregorian | julian | regnal | radiocarbon_calibrated | unspecified …
    dating_method   TEXT,                         -- historical | radiocarbon | dendrochronology | luminescence | stratigraphic | stylistic | …
    jdn_start       INTEGER,                      -- Julian Day Number, only when day precision is known
    jdn_end         INTEGER,
    time_basis      TEXT NOT NULL DEFAULT 'calendar' CHECK (time_basis IN
                      ('calendar',              -- a calendar year/date given by the source
                       'bp_1950',               -- source explicitly states BP (before 1950)
                       'years_before_source')), -- source says "X years ago"; stored relative to 1950 = POC conversion assumption
    claim_id        TEXT NOT NULL REFERENCES claim(claim_id),
    CHECK (earliest_start IS NULL OR latest_start IS NULL OR earliest_start <= latest_start),
    CHECK (earliest_end   IS NULL OR latest_end   IS NULL OR earliest_end   <= latest_end),
    CHECK (earliest_start IS NULL OR latest_end   IS NULL OR earliest_start <= latest_end),
    CHECK (earliest_start IS NULL OR earliest_end IS NULL OR earliest_start <= earliest_end),
    CHECK (latest_start   IS NULL OR latest_end   IS NULL OR latest_start   <= latest_end)
);
CREATE INDEX ix_time_entity ON temporal_extent(entity_id);
CREATE INDEX ix_time_bounds ON temporal_extent(earliest_start, latest_end);

-- ---------------------------------------------------------------------
-- POV / GRAPH — typed relations between any two entities.
-- ---------------------------------------------------------------------
CREATE TABLE predicate (
    predicate_id      TEXT PRIMARY KEY,           -- 'has_function'
    label             TEXT NOT NULL,
    inverse_label     TEXT,
    category          TEXT NOT NULL CHECK (category IN ('geo','time','classification','association','structural')),
    description       TEXT,
    wikidata_property TEXT,                       -- closest Wikidata property, for LOD export
    cidoc_crm         TEXT                        -- closest CIDOC-CRM property
);

CREATE TABLE relation (
    relation_id   INTEGER PRIMARY KEY,
    subject_id    TEXT NOT NULL REFERENCES entity(entity_id),
    predicate_id  TEXT NOT NULL REFERENCES predicate(predicate_id),
    object_id     TEXT NOT NULL REFERENCES entity(entity_id),
    qualifiers    TEXT NOT NULL DEFAULT '{}',     -- JSON: role detail, ordinal, phase …
    claim_id      TEXT NOT NULL REFERENCES claim(claim_id)
);
CREATE INDEX ix_rel_subject ON relation(subject_id, predicate_id);
CREATE INDEX ix_rel_object ON relation(predicate_id, object_id);

-- Lightweight, uncontrolled labels (folksonomy / editorial convenience only).
CREATE TABLE entity_tag (
    entity_id  TEXT NOT NULL REFERENCES entity(entity_id),
    tag        TEXT NOT NULL,
    PRIMARY KEY (entity_id, tag)
);

-- ---------------------------------------------------------------------
-- CONVENIENCE VIEWS
-- ---------------------------------------------------------------------
-- Every factual row with its claim status, for "show all versions" UIs.
CREATE VIEW v_temporal_claims AS
SELECT t.*, c.rank, c.status, c.confidence, c.dispute_group, c.note
FROM temporal_extent t JOIN claim c ON c.claim_id = t.claim_id;

CREATE VIEW v_relation_claims AS
SELECT r.*, c.rank, c.status, c.confidence, c.dispute_group, c.note
FROM relation r JOIN claim c ON c.claim_id = r.claim_id;

-- Usable claims for default views: not deprecated (rank) and not rejected (status).
-- disputed / alternative / needs_verification claims ARE used, but flagged ('uncertain').

-- Transitive closure of hierarchical predicates (broader / part_of),
-- used to expand POV concepts and GEO places to their descendants.
CREATE VIEW v_hierarchy AS
WITH RECURSIVE closure(descendant_id, ancestor_id, depth, uncertain) AS (
    SELECT entity_id, entity_id, 0, 0 FROM entity
    UNION
    SELECT r.subject_id, c.ancestor_id, c.depth + 1,
           MAX(c.uncertain, CASE WHEN cl.status IN ('disputed','alternative','needs_verification') THEN 1 ELSE 0 END)
    FROM relation r
    JOIN closure c ON r.object_id = c.descendant_id
    JOIN claim cl ON cl.claim_id = r.claim_id
    WHERE r.predicate_id IN ('broader','part_of') AND cl.rank <> 'deprecated' AND cl.status <> 'rejected' AND c.depth < 20
)
SELECT descendant_id, ancestor_id, MIN(depth) AS depth, MIN(uncertain) AS uncertain_only
FROM closure GROUP BY descendant_id, ancestor_id;

-- GEO containment: every place an entity is (transitively) in.
-- Follows located_in / part_of / found_at / occurred_at, then place located_in/part_of chains.
-- 'overlaps' (e.g. Turkey ~ Europe) is deliberately NOT followed.
-- held_by (current keeper of an object) is NOT containment.
-- basis      = basis of the FIRST edge (e.g. 'political (modern state)', 'historical/cultural region (curated)')
-- uncertain_only = 1 if every path to the place uses a disputed/alternative/needs_verification claim.
CREATE VIEW v_geo_closure AS
WITH RECURSIVE g(entity_id, place_id, depth, basis, uncertain) AS (
    SELECT r.subject_id, r.object_id, 1,
           COALESCE(json_extract(r.qualifiers, '$.basis'), r.predicate_id),
           CASE WHEN c.status IN ('disputed','alternative','needs_verification') THEN 1 ELSE 0 END
    FROM relation r JOIN claim c ON c.claim_id = r.claim_id
    WHERE r.predicate_id IN ('located_in','part_of','found_at','occurred_at')
      AND c.rank <> 'deprecated' AND c.status <> 'rejected'
    UNION
    SELECT g.entity_id, r.object_id, g.depth + 1, g.basis,
           MAX(g.uncertain, CASE WHEN c.status IN ('disputed','alternative','needs_verification') THEN 1 ELSE 0 END)
    FROM g
    JOIN relation r ON r.subject_id = g.place_id
    JOIN claim c ON c.claim_id = r.claim_id
    WHERE r.predicate_id IN ('located_in','part_of') AND c.rank <> 'deprecated' AND c.status <> 'rejected' AND g.depth < 12
)
SELECT entity_id, place_id, MIN(depth) AS depth, GROUP_CONCAT(DISTINCT basis) AS bases, MIN(uncertain) AS uncertain_only
FROM g GROUP BY entity_id, place_id;

-- Effective point of an entity: its own usable coordinates (primary / verified find_spot),
-- otherwise those of the entity it is part_of / was found_at. 'via' and the two claim ids
-- say WHY a point is shown and which evidence supports it. reported_point and
-- gazetteer_point are never used here (not verified / QA only).
CREATE VIEW v_entity_point AS
SELECT l.entity_id, l.lat, l.lon, l.role, 'own' AS via, l.entity_id AS point_entity_id,
       l.claim_id AS location_claim_id, NULL AS via_claim_id,
       CASE WHEN c.status IN ('disputed','alternative','needs_verification') THEN 1 ELSE 0 END AS uncertain
FROM location l JOIN claim c ON c.claim_id = l.claim_id
WHERE c.rank <> 'deprecated' AND c.status <> 'rejected' AND l.role IN ('primary','find_spot')
UNION ALL
SELECT r.subject_id, l.lat, l.lon, l.role, r.predicate_id, r.object_id, l.claim_id, r.claim_id,
       CASE WHEN c.status IN ('disputed','alternative','needs_verification')
              OR rc.status IN ('disputed','alternative','needs_verification') THEN 1 ELSE 0 END
FROM relation r
JOIN claim rc ON rc.claim_id = r.claim_id AND rc.rank <> 'deprecated' AND rc.status <> 'rejected'
JOIN location l ON l.entity_id = r.object_id AND l.role IN ('primary','find_spot')
JOIN claim c ON c.claim_id = l.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
WHERE r.predicate_id IN ('part_of','found_at')
  AND NOT EXISTS (SELECT 1 FROM location own JOIN claim oc ON oc.claim_id = own.claim_id
                  WHERE own.entity_id = r.subject_id AND own.role IN ('primary','find_spot')
                    AND oc.rank <> 'deprecated' AND oc.status <> 'rejected');
