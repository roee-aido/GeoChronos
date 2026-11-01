"""GeoChronos query layer: GEO-First, TIME-First and POV-First over ONE database.

Every function returns plain dicts so the same calls can back an API, the
validation suite and the query examples. SQL is kept close to what would run
on PostgreSQL/PostGIS (see QUERY_EXAMPLES.md for the PostGIS forms).
"""
import math
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import timefmt as tf  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "build" / "geochronos.sqlite"          # profile full
BASE_DB_PATH = ROOT / "build" / "geochronos_base.sqlite"  # profile base (regression seed)
USABLE = "c.rank <> 'deprecated' AND c.status <> 'rejected'"
BIG = 1e18

# Roles that mean "the thing was being made / used / happening" (default TIME semantics).
# Heritage-history roles (discovery, excavation, restoration, relocation, damage, reuse) are opt-in.
ACTIVE_ROLES = ("construction", "creation", "use", "occupation", "existence", "event", "deposition",
                "destruction", "reign", "life", "first_record")
CLASSIFICATION_PREDICATES = ("instance_of", "has_form", "has_function", "made_of", "culture", "period",
                             "polity", "dynasty", "religion", "theme")


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.create_function("haversine_km", 4, haversine_km, deterministic=True)
    return con


def _kinds_sql(kinds):
    return ",".join("?" * len(kinds))


# ------------------------------------------------------------------ GEO ----

def geo_in_place(con, place_id, kinds=("item",)):
    """Everything (transitively) located in a place of the place graph.
    'bases' says on what basis (political state, administrative, curated historical region, …);
    'uncertain_only' = 1 if every path relies on a disputed/alternative/needs_verification claim."""
    sql = f"""
        SELECT e.entity_id, e.canonical_name, g.depth, g.bases, g.uncertain_only
        FROM v_geo_closure g JOIN entity e ON e.entity_id = g.entity_id
        WHERE g.place_id = ? AND e.kind IN ({_kinds_sql(kinds)})
        ORDER BY e.canonical_name"""
    return [dict(r) for r in con.execute(sql, (place_id, *kinds))]


def geo_bbox(con, south, west, north, east, kinds=("item",)):
    """Everything whose effective point falls in a bounding box (PostGIS: ST_MakeEnvelope + ST_Intersects)."""
    sql = f"""
        SELECT e.entity_id, e.canonical_name, AVG(p.lat) AS lat, AVG(p.lon) AS lon,
               GROUP_CONCAT(DISTINCT p.via || ':' || p.point_entity_id) AS via, MAX(p.uncertain) AS uncertain,
               GROUP_CONCAT(DISTINCT p.location_claim_id) AS location_claims
        FROM v_entity_point p JOIN entity e ON e.entity_id = p.entity_id
        WHERE p.lat BETWEEN ? AND ? AND p.lon BETWEEN ? AND ? AND e.kind IN ({_kinds_sql(kinds)})
        GROUP BY e.entity_id ORDER BY e.canonical_name"""
    return [dict(r) for r in con.execute(sql, (south, north, west, east, *kinds))]


def geo_near(con, lat, lon, km, kinds=("item",)):
    """Everything within km of a point (PostGIS: ST_DWithin on geography)."""
    sql = f"""
        SELECT e.entity_id, e.canonical_name, MIN(haversine_km(?, ?, p.lat, p.lon)) AS km,
               GROUP_CONCAT(DISTINCT p.via || ':' || p.point_entity_id) AS via, MAX(p.uncertain) AS uncertain
        FROM v_entity_point p JOIN entity e ON e.entity_id = p.entity_id
        WHERE e.kind IN ({_kinds_sql(kinds)})
        GROUP BY e.entity_id HAVING km <= ? ORDER BY km"""
    return [dict(r) for r in con.execute(sql, (lat, lon, *kinds, km))]


def geo_currently_held_in(con, place_id):
    """Movable objects whose current keeper is located in a place (separate from find-spot GEO)."""
    sql = """
        SELECT o.entity_id, o.canonical_name, org.canonical_name AS keeper
        FROM relation r
        JOIN claim c ON c.claim_id = r.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
        JOIN entity o ON o.entity_id = r.subject_id
        JOIN entity org ON org.entity_id = r.object_id
        JOIN v_geo_closure g ON g.entity_id = org.entity_id AND g.place_id = ?
        WHERE r.predicate_id = 'held_by'
        GROUP BY o.entity_id ORDER BY o.canonical_name"""
    return [dict(r) for r in con.execute(sql, (place_id,))]


# ----------------------------------------------------------------- TIME ----

def time_overlap(con, start_hist, end_hist, mode="possible", roles=ACTIVE_ROLES, kinds=("item",), open_end="evidence"):
    """Entities with a temporal extent overlapping [start_hist, end_hist] (historical years, negative = BCE).

    mode='possible': the uncertain range COULD overlap (earliest_start <= qEnd AND latest_end >= qStart).
    mode='certain' : it MUST overlap          (latest_start  <= qEnd AND earliest_end >= qStart).
    open_end: how an unknown end (latest_end NULL) is read in 'possible' mode:
        'evidence'  (default) -> only as far as attested: earliest_end, else the start.
        'unbounded'           -> +infinity (maximal possibility; e.g. "inhabited to at least 8000 BCE").
    Returns one row per entity with the best-ranked matching claim and provenance flags.
    """
    qs, qe = float(tf.hist_to_astro(start_hist)), float(tf.hist_to_astro(end_hist))
    cond = time_condition(mode, open_end)
    role_ph = ",".join(f":r{i}" for i in range(len(roles)))
    kind_ph = ",".join(f":k{i}" for i in range(len(kinds)))
    sql = f"""
        SELECT e.entity_id, e.canonical_name, t.*, c.rank, c.status, c.confidence, c.dispute_group
        FROM temporal_extent t
        JOIN claim c ON c.claim_id = t.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
        JOIN entity e ON e.entity_id = t.entity_id
        WHERE t.role IN ({role_ph}) AND e.kind IN ({kind_ph}) AND {cond}"""
    params = {"qs": qs, "qe": qe, **{f"r{i}": r for i, r in enumerate(roles)}, **{f"k{i}": k for i, k in enumerate(kinds)}}
    best, counts = {}, {}
    order = {"preferred": 0, "normal": 1}
    status_order = {"accepted": 0, "alternative": 1, "disputed": 2, "needs_verification": 3}
    for r in con.execute(sql, params):
        r = dict(r)
        eid = r["entity_id"]
        counts[eid] = counts.get(eid, 0) + 1
        r["_key"] = (order.get(r["rank"], 2), status_order.get(r["status"], 4))
        if eid not in best or r["_key"] < best[eid]["_key"]:
            best[eid] = r
    for eid, r in best.items():
        r["_n"] = counts[eid]
    out = []
    for r in sorted(best.values(), key=lambda x: (x["earliest_start"] if x["earliest_start"] is not None else -BIG)):
        out.append({
            "entity_id": r["entity_id"], "canonical_name": r["canonical_name"], "role": r["role"],
            "label": r["label"], "rank": r["rank"], "status": r["status"], "confidence": r["confidence"],
            "matching_claims": r["_n"], "open_ended": r["latest_end"] is None,
            "open_start": r["earliest_start"] is None, "time_basis": r["time_basis"],
            "uncertain": r["status"] in ("disputed", "alternative", "needs_verification"),
            "civil": tf.format_civil(r), "bp": tf.format_bp(r), "hebrew": tf.format_hebrew(r),
        })
    return out


def time_condition(mode="possible", open_end="evidence"):
    """The SQL predicate used by time_overlap (exposed so documentation examples can be checked against it).

    possible / evidence  (default): unknown bounds reach only as far as the evidence goes
        start := COALESCE(earliest_start, latest_start, earliest_end, latest_end)
        end   := COALESCE(latest_end, earliest_end, latest_start, earliest_start)
    possible / unbounded: unknown start = -inf, unknown end = +inf (maximal possibility)
    certain: the interval [latest_start, earliest_end] must be known, non-empty and intersect the window.
    """
    if mode == "certain":
        return ("t.latest_start IS NOT NULL AND t.earliest_end IS NOT NULL AND t.latest_start <= t.earliest_end "
                "AND t.latest_start <= :qe AND t.earliest_end >= :qs")
    if open_end == "unbounded":
        return "COALESCE(t.earliest_start, -1e18) <= :qe AND COALESCE(t.latest_end, 1e18) >= :qs"
    return ("COALESCE(t.earliest_start, t.latest_start, t.earliest_end, t.latest_end) <= :qe AND "
            "COALESCE(t.latest_end, t.earliest_end, t.latest_start, t.earliest_start) >= :qs")


def time_unknown(con, roles=ACTIVE_ROLES, kinds=("item",)):
    """Entities with NO usable extent in the given roles: TIME-First must show them as 'date unknown', not drop them."""
    role_ph = ",".join("?" * len(roles))
    sql = f"""
        SELECT e.entity_id, e.canonical_name FROM entity e
        WHERE e.kind IN ({_kinds_sql(kinds)}) AND e.entity_id NOT IN (
            SELECT t.entity_id FROM temporal_extent t JOIN claim c ON c.claim_id = t.claim_id
            WHERE t.role IN ({role_ph}) AND {USABLE})
        ORDER BY e.canonical_name"""
    return [dict(r) for r in con.execute(sql, (*kinds, *roles))]


# ------------------------------------------------------------------ POV ----

def pov(con, concept_id, predicates=CLASSIFICATION_PREDICATES, narrower=True, kinds=("item",)):
    """Entities classified under a concept/culture/period/religion (optionally incl. narrower concepts)."""
    pred_ph = ",".join("?" * len(predicates))
    hier = "JOIN v_hierarchy h ON h.descendant_id = r.object_id AND h.ancestor_id = ?" if narrower else ""
    where_obj = "" if narrower else "AND r.object_id = ?"
    sql = f"""
        SELECT e.entity_id, e.canonical_name,
               GROUP_CONCAT(DISTINCT r.predicate_id || ':' || o.canonical_name) AS via,
               MAX(CASE WHEN c.status IN ('disputed','needs_verification') THEN 1 ELSE 0 END) AS has_uncertain_link
        FROM relation r {hier}
        JOIN claim c ON c.claim_id = r.claim_id AND c.rank <> 'deprecated' AND c.status <> 'rejected'
        JOIN entity e ON e.entity_id = r.subject_id
        JOIN entity o ON o.entity_id = r.object_id
        WHERE r.predicate_id IN ({pred_ph}) AND e.kind IN ({_kinds_sql(kinds)}) {where_obj}
        GROUP BY e.entity_id ORDER BY e.canonical_name"""
    params = ([concept_id] if narrower else []) + list(predicates) + list(kinds) + ([] if narrower else [concept_id])
    return [dict(r) for r in con.execute(sql, params)]


def pov_related_to(con, entity_id):
    """Everything linked to an entity (e.g. a person) by any relation, with claim status."""
    sql = """
        SELECT e.entity_id, e.canonical_name, r.predicate_id, c.status, c.rank, c.dispute_group
        FROM relation r JOIN claim c ON c.claim_id = r.claim_id
        JOIN entity e ON e.entity_id = r.subject_id
        WHERE r.object_id = ? AND c.rank <> 'deprecated' AND c.status <> 'rejected' ORDER BY e.canonical_name"""
    return [dict(r) for r in con.execute(sql, (entity_id,))]


# ------------------------------------------------------------- combined ----

def combined(con, place_id=None, concept_id=None, time_range=None, kinds=("item",)):
    """Intersect the three views: the core GeoChronos operation."""
    sets = []
    if place_id:
        sets.append({r["entity_id"] for r in geo_in_place(con, place_id, kinds)})
    if concept_id:
        sets.append({r["entity_id"] for r in pov(con, concept_id, kinds=kinds)})
    rows_t = {}
    if time_range:
        rows_t = {r["entity_id"]: r for r in time_overlap(con, *time_range, kinds=kinds)}
        sets.append(set(rows_t))
    ids = set.intersection(*sets) if sets else set()
    names = {r[0]: r[1] for r in con.execute("SELECT entity_id, canonical_name FROM entity")}
    return [dict({"entity_id": i, "canonical_name": names[i]}, **({k: rows_t[i][k] for k in ("civil", "status")} if i in rows_t else {}))
            for i in sorted(ids, key=lambda x: names[x])]


# ----------------------------------------------------------- provenance ----

def claims_for(con, entity_id, statement_type=None):
    """All claims (all ranks) about an entity with their evidence — the 'show me why' view."""
    sql = """
        SELECT c.claim_id, c.statement_type, c.rank, c.status, c.confidence, c.dispute_group, c.note,
               GROUP_CONCAT(ev.source_id || COALESCE(' [' || ev.locator || ']', ''), '; ') AS evidence
        FROM claim c LEFT JOIN claim_evidence ev ON ev.claim_id = c.claim_id
        WHERE c.entity_id = ? AND (? IS NULL OR c.statement_type = ?)
        GROUP BY c.claim_id ORDER BY c.statement_type, c.dispute_group, c.rank"""
    return [dict(r) for r in con.execute(sql, (entity_id, statement_type, statement_type))]


def dispute(con, group):
    sql = """
        SELECT c.entity_id, c.rank, c.status, c.confidence, c.note,
               t.label AS temporal_label, t.earliest_start, t.latest_start, t.earliest_end, t.latest_end,
               t.precision, t.qualifier, t.jdn_start, t.jdn_end, t.source_calendar,
               r.predicate_id, r.object_id
        FROM claim c
        LEFT JOIN temporal_extent t ON t.claim_id = c.claim_id
        LEFT JOIN relation r ON r.claim_id = c.claim_id
        WHERE c.dispute_group = ? ORDER BY c.rank DESC"""
    return [dict(r) for r in con.execute(sql, (group,))]
