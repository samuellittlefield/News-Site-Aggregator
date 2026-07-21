# Test Cases: Per-Source Ingestion Health Tracking

**Slug:** `ingestion-health` &nbsp; **Source:** `02-acceptance-criteria.md`

> **Note:** unlike earlier feature docs in this repo, a real pytest harness now exists (`backend/tests/`, Postgres-backed, respx-mocked, shipped via `test-harness-ci`). Backend cases below are written as automated pytest, following the pattern in `test_kalshi_upsert.py` (docstring cites AC/TC IDs, `db`/`respx_router` fixtures, async test functions). Frontend still has no Vitest harness (that's a separate, unshipped roadmap chore) — those cases stay manual/click-through with an automation note.

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2 |
| AC-3 | TC-3 |
| AC-4 | TC-4 |
| AC-5 | TC-5 |
| AC-6 | TC-6 |
| AC-7 | TC-8 |
| AC-8 | TC-9 |
| (coverage) | TC-7 |

## Backend

### TC-1 — Successful run upserts a `success` SourceRun row (covers AC-1)
- **Type:** unit (service function), `backend/tests/test_source_run.py`
- **Setup:** empty `source_runs` table
- **Steps:**
  1. Call `record_success(db, source_id="kalshi_job", label="Kalshi", cadence_minutes=10, item_count=4)`
  2. Query `SourceRun` filtered by `source_id="kalshi_job"`
- **Expected Result:** exactly one row, `status="success"`, `last_success_at` and `last_run_at` set to ~now, `item_count=4`, `error_message` is `None`
- **Automation note:** `backend/tests/test_source_run.py`, uses the `db` fixture from `conftest.py`

### TC-2 — Failed run upserts a `failure` SourceRun row (covers AC-2)
- **Type:** unit + integration
- **Setup:** mock a `refresh_*` function's upstream call (e.g. `votehub.py`'s endpoint via `respx_router`) to raise/return an error
- **Steps:**
  1. Call the real scheduler function, e.g. `await scheduler.refresh_votehub()`, with the mocked upstream failing
  2. Query `SourceRun` for `source_id="votehub_job"`
  3. Separately assert no other job's execution was affected (call a second, unrelated `refresh_*` function in the same test and confirm it completes normally)
- **Expected Result:** `SourceRun` row shows `status="failure"` with a non-empty `error_message`; the unrelated second job still completes and records its own `success` row — isolation intact
- **Automation note:** `backend/tests/test_source_run.py` or alongside existing per-source test files

### TC-3 — Recording failure never propagates (covers AC-3)
- **Type:** unit, force a DB-layer error during recording
- **Setup:** monkeypatch/mock the `SourceRun` upsert call inside `record_success`/`record_failure` to raise (simulating a DB blip at record time)
- **Steps:**
  1. Call `record_success(...)` (or `record_failure(...)`) with the DB write mocked to raise
  2. Assert the call itself does not raise out to the caller
  3. Assert a log line was emitted (via `caplog` or similar) instead
- **Expected Result:** no exception propagates; the failure is swallowed and logged only

### TC-4 — Re-run upserts, does not duplicate (covers AC-4)
- **Type:** unit, mirrors `test_kalshi_upsert.py`'s idempotency pattern
- **Steps:**
  1. Call `record_success(db, source_id="earthquakes_job", ...)` twice in a row with different `item_count` values
  2. Query `SourceRun` filtered by `source_id="earthquakes_job"`
- **Expected Result:** exactly one row exists; its `item_count` reflects the second call, not two rows

### TC-5 — API returns one entry per registered source with cadence (covers AC-5)
- **Type:** integration (`TestClient`), `backend/tests/test_routers_smoke.py` or a new `test_status_sources.py`
- **Setup:** seed a few `SourceRun` rows (mix of success/failure)
- **Steps:**
  1. `GET /api/status/sources`
  2. Inspect response body
- **Expected Result:** 200; one entry per source_id in `SOURCE_CADENCE`; each entry includes source id/label, status, `last_success_at`, `error_message` (nullable), `item_count` (nullable), `cadence_minutes`

### TC-6 — Never-run source appears as distinct state, not omitted or 500 (covers AC-6)
- **Type:** integration, empty-DB variant of TC-5
- **Setup:** empty `source_runs` table (fresh DB, mirrors `test_congress_forecast_empty_db`/`test_list_trends_empty_db` pattern already in `test_routers_smoke.py`)
- **Steps:**
  1. `GET /api/status/sources` against an empty table
- **Expected Result:** 200 (not 500); every source in `SOURCE_CADENCE` appears with `status="never_run"` and null timestamps — list length equals the number of registered sources, none omitted

### TC-7 — Instrumentation coverage matches registered jobs (covers scope note in AC edge cases)
- **Type:** unit, guards against silent drift
- **Steps:**
  1. Import `start_scheduler` registration and extract the set of `id=` values passed to `scheduler.add_job(...)`
  2. Compare against the keys of `SOURCE_CADENCE` in `source_run.py`
- **Expected Result:** the two sets are identical — catches a newly added scheduler job that forgot health-tracking instrumentation, or a stale `SOURCE_CADENCE` entry for a job that was removed. Also assert `refresh_breakout`'s id (if any) is deliberately absent from both, or present in both — not silently mismatched.

## Frontend

### TC-8 — Data Sources panel shows freshness and flags stale/failing sources (covers AC-7)
- **Type:** manual/click-through
- **Steps:**
  1. Run `npm run dev` in `frontend/`, seed backend with a mix of fresh-success, stale-success (older than cadence), and failing sources
  2. Navigate to the Status page
- **Expected Result:** each source shows relative last-updated time; stale and failing sources are visually flagged (e.g. red indicator), fresh ones are not
- **Automation note:** target `frontend/src/components/SourceHealthSection.test.tsx` with Vitest + React Testing Library once that harness exists (currently unshipped per roadmap chores)

### TC-9 — Failing source shows its error message in the UI (covers AC-8)
- **Type:** manual/click-through
- **Steps:**
  1. Seed a `SourceRun` row with `status="failure"` and a realistic error message
  2. Load the Status page
- **Expected Result:** the error message (or a sanitized/truncated form) is visible on that source's row without checking server logs
- **Automation note:** same Vitest note as TC-8

## Edge Cases & Failure Modes
- Upstream source down/malformed (existing per-job try/except) → job still records a `failure` row and doesn't starve other jobs (TC-2)
- DB write failure during recording itself → swallowed, never propagates (TC-3)
- Re-run after success or failure → always exactly one row per source (TC-4)
- Fresh deploy, jobs haven't fired yet → distinct `never_run` state, no crash (TC-6)
- A job that returns no count (`refresh_climate`, `refresh_faa`) → `item_count` stays null, doesn't error
- Scheduler job list drifts from `SOURCE_CADENCE` map over time → caught by TC-7, not just informally noticed

## Regression Check
- Existing `/api/status` (third-party `ServiceStatus`) endpoint and `ServiceStatusSection` — unaffected, but smoke-check that both sections render together on `StatusPage.tsx` without layout/name collisions
- Existing `test_routers_smoke.py` suite — should still pass unmodified (new tests are additive, not replacing existing ones)
- Scheduler startup (`start_scheduler()`) — confirm all existing jobs still register correctly after adding recording calls; a syntax/import error in `source_run.py` would break every job's import, not just health tracking

## Sign-off
- [ ] All test cases pass (`pytest backend/tests/` for TC-1 through TC-7; manual click-through for TC-8/TC-9)
- [ ] Samuel has reviewed results before merge to main
