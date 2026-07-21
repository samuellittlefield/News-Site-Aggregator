# Implementation Plan: Per-Source Ingestion Health Tracking

**Slug:** `ingestion-health` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Add a `SourceRun` model (one upserted row per scheduler job id) and a small helper that records success/failure around each `refresh_*` function body in `scheduler.py`, without touching the existing outer try/except isolation. Expose it via a new `GET /api/status/sources` route, and add a "Data Sources" panel to `StatusPage.tsx` next to the existing third-party `ServiceStatusSection`.

## Backend Changes
*(Python 3.9 — use `Optional[...]`, not `X | Y`)*

| File | Change |
|---|---|
| `backend/app/models.py` | New `SourceRun` model: `id` (PK), `source_id` (String, unique, matches `scheduler.add_job(id=...)`), `label` (String, human-readable name), `status` (String: `success`\|`failure`\|`never_run`), `last_success_at` (DateTime, nullable), `last_run_at` (DateTime, nullable), `error_message` (Text, nullable), `item_count` (Integer, nullable), `cadence_minutes` (Integer — expected interval, so staleness is judged per-source) |
| `backend/app/services/source_run.py` | New. `record_success(db, source_id, label, cadence_minutes, item_count=None)` and `record_failure(db, source_id, label, cadence_minutes, error)` — both upsert-by-`source_id`, both wrap their own DB write in a try/except that only logs (AC-3: recording can never raise). A `SOURCE_CADENCE` dict or similar maps each `source_id` → its `IntervalTrigger` minutes, single source of truth shared with `scheduler.py`'s job registration so the two can't drift apart. |
| `backend/app/models.py` + `backend/alembic/versions/` | New migration `<hash>_add_source_run.py`, revises the current head (`b2f1a7c4d9e3`). Additive-only (new table), safe on existing data — no backfill needed since the table starts empty and AC-6 already requires a "never_run" state for rows that don't exist yet. |
| `backend/app/routers/status.py` | Add `GET /api/status/sources` to the existing router (same `/api/status` prefix as third-party status — natural sibling, not a new router). Query `SourceRun`, and for any registered `source_id` with no row yet, synthesize a `never_run` entry (AC-6) rather than omitting it — the canonical list of registered ids comes from the same `SOURCE_CADENCE` mapping in `source_run.py`, not from querying jobs off the live `scheduler` object (keeps the route usable even if the scheduler is disabled, e.g. under `DISABLE_SCHEDULER=1` in tests). |
| `backend/app/scheduler.py` | Every `refresh_*` function that's actually registered in `start_scheduler()` gets two additions: a `record_success(...)` call at the end of its try block, and a `record_failure(...)` call in its except block (alongside the existing `logger.exception`). `refresh_faa` needs a `db = SessionLocal()` / `finally: db.close()` added since it currently has none — needed purely to write the `SourceRun` row. `refresh_breakout` is explicitly NOT instrumented (not registered via `add_job` today — confirm this is still true; if it's dead code entirely, flag to Samuel rather than silently leaving it out). |

Failure isolation: recording happens *inside* each function's existing try/except, on both branches — it does not change what's caught, does not re-raise, and per AC-3 is itself wrapped so a DB hiccup during recording can't turn into an unhandled exception inside the scheduler's job.

## Frontend Changes
| File | Change |
|---|---|
| `frontend/src/api/client.ts` | New `getSourceRuns()` calling `GET /api/status/sources`, returning a typed list (mirror the existing `ServiceStatus` typing pattern already in this file) |
| `frontend/src/components/SourceHealthSection.tsx` | New component — per-source row: label, relative last-updated time ("3h ago" / "never run"), red flag when `status=failure` or `(now - last_success_at) > cadence_minutes`, truncated error message shown when failing (AC-7, AC-8) |
| `frontend/src/pages/StatusPage.tsx` | Add `<SourceHealthSection />` alongside the existing `<ServiceStatusSection />` |

## Data Model / Migration Notes
- `SourceRun` is upsert-by-`source_id` (one current-state row per source, per the plan's explicit non-goal of history/logging) — migration just creates the table, no data migration needed.
- `cadence_minutes` is duplicated from `scheduler.py`'s `IntervalTrigger` values at the point each job is registered; keep the `SOURCE_CADENCE` dict as the single place both the scheduler registration and the route read from, so a future cadence change (e.g. bumping `kalshi_job` from 10m to 15m) doesn't require updating two places and risking drift.
- `item_count` stays nullable — several jobs (e.g. `refresh_climate`, `refresh_faa`) don't currently return a count; don't force a refactor of those functions just to populate this field (per AC edge cases).

## Sequencing
1. Migration: add `SourceRun` table
2. `source_run.py` service (record_success/record_failure + `SOURCE_CADENCE` map)
3. Instrument `scheduler.py`'s `refresh_*` functions one at a time (add `db` session to `refresh_faa` as part of this step)
4. `GET /api/status/sources` route in `status.py`
5. Frontend: `client.ts` → `SourceHealthSection.tsx` → wire into `StatusPage.tsx`

## Documentation Updates
- [ ] `SOURCES.md` — add a short note under the existing ingestion-pattern description that every registered scheduler job now records its own health via `SourceRun`; doesn't need a full source row since this isn't a new upstream data source, just cross-cutting instrumentation of existing ones.
- [ ] `.env.example` — not needed, no new env vars/secrets.

## Risks / Rollback
- Migration is additive-only (new table) — safe to roll forward; rollback is a straightforward `alembic downgrade` if needed, no data loss risk since nothing existing is touched.
- Main risk is accidentally breaking the failure-isolation guarantee while adding recording calls to ~15-20 functions by hand — mitigate by keeping the `record_success`/`record_failure` calls as thin, defensively-wrapped one-liners (see AC-3) rather than restructuring the existing try/except bodies.
- If `refresh_breakout` turns out to still be scheduled somewhere non-obvious, it'll show up as permanently `never_run` in the UI — low severity, easy to spot and fix by adding instrumentation to it too.

## Test Plan Pointer
See `04-test-cases.md` for the cases this implementation must satisfy. Given the shipped `test-harness-ci` (pytest + Postgres + respx in `backend/tests/`), these should be written as real automated pytest cases, not manual curl scripts.
