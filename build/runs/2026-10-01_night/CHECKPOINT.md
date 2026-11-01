# Night run checkpoint (updated after each unit of work)

Run folder: build/runs/2026-10-01_night/  · Time zone: Asia/Jerusalem (IDT, UTC+03:00)
Restore point: backups/2026-10-01_2213_pre-night/ (SHA256SUMS.txt inside). No git repository exists in the project.

| # | Unit | Status | Evidence |
|---|---|---|---|
| 1 | Baseline run (timefmt, build, validate) | DONE 22:13–22:14 — all exit 0, 37/37 | baseline/run_log.json, baseline/*.stdout.txt |
| 2 | Semantics & quality tests + fixes | DONE (logged run after_phase2 started 22:33:06 per run_log.json) — schema views/time checks, build refactor (multi-snapshot, supersession, calibrated Wikidata dates, find-spot verification, no auto-high), geoquery semantics; 38 unit tests OK, 37/37 validation | after_phase2/run_log.json, tests/ |
| 3 | Seed hardening & curation queue | DONE (literature.json written 22:38; curation_manual.csv last modified 22:56 — per file mtimes) — flagship evidence (Egypt MoTA, English Heritage, DAI blog, 6 papers via OpenAlex abstracts); Caral QID verified; 2 bad Hebrew labels rejected; Qumran/Ahu kept unknown; mapping rules (has_style, named_after, P2596->period, P361->culture); data/seed/curation_manual.csv; NOTE seed JSON re-serialised by a patch (content intact, formatting changed) | data/seed/literature.json, data/raw/openalex/ |
| 4 | Ingestion pipeline | DONE (INGESTION_REPORT.md written) — scripts/ingest.py; snapshots: wikidata legacy + 2026-10-01T222038+0300, pleiades 2026-10-01T222258+0300, hebcal fixtures; idempotence tests pass (tests/test_provenance_identity.py) | data/raw/*, data/staging/* |
| 5 | Measured expansion (≤150 Items total) | DONE (expansion snapshots 22:54 and 22:55 per snapshot ids; checkpoint written 22:58) — +38 Items, +2 events (95 Items in profile full); seed: items_expansion.json, vocabulary_expansion.json, wikidata_targets_expansion.json; snapshots wikidata 2026-10-01T225416+0300, pleiades 2026-10-01T225549+0300; 20/20 expansion checks; base suite 37/37 on base and full DBs | build/validation_expansion_report.md |
| 6 | Reports & docs | DONE — final logged run final_state/ 23:10:30–23:11:21 (all exit 0: validate 37/37, expansion 20/20, unittest 40/40); reports written after it (text only) | NIGHT_REPORT.md, HANDOFF.md, SPEC_INPUTS.md, DATA_QUALITY_REPORT.md, INGESTION_REPORT.md, CURATION_QUEUE.csv, TESTS_ADDED.md, SEED_DIFF.md |

Note: times in this file come from run logs, snapshot ids or file modification times; no execution time is estimated.

STATUS: all six units complete. Stopping point and follow-up tasks: HANDOFF.md.
