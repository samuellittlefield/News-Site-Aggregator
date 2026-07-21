# Acceptance Criteria: Per-Source Ingestion Health Tracking

**Slug:** `ingestion-health` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: Successful run is recorded
- **Given** a scheduled job (e.g. `votehub_job`) is registered in `start_scheduler()`
- **When** its `refresh_*` function completes without raising
- **Then** the corresponding `SourceRun` row (keyed by the same `source_id` used in `scheduler.add_job(..., id=...)`) is upserted with `status=success`, `finished_at` set to the completion time, and an item count where the function already returns/logs one (e.g. `house_polls` → `new_polls`, `earthquakes` → count)

### AC-2: Failed run is recorded without breaking isolation
- **Given** a scheduled job's `refresh_*` function raises inside its existing try/except
- **When** the exception is caught (as it is today, logged via `logger.exception`)
- **Then** the `SourceRun` row for that `source_id` is upserted with `status=failure` and the exception message, **and** the outer scheduler loop is completely unaffected — no other job's execution, current or next-scheduled, is delayed or skipped

### AC-3: Recording itself can never break a job
- **Given** the `SourceRun` write (DB insert/update) itself fails — e.g. a DB connectivity blip at the moment of recording
- **When** that happens during either the success or failure recording path
- **Then** the recording error is caught and logged, and does not propagate up to crash or fail the ingestion job it was trying to record — the job's own success/failure to the rest of the app is unaffected by a health-tracking bug

### AC-4: Upsert, not append — re-runs update the same row
- **Given** a source has an existing `SourceRun` row from a prior run
- **When** the job runs again (success or failure)
- **Then** the existing row is updated in place (by `source_id`), not duplicated — `GET /api/status/sources` always returns exactly one row per registered job id

### AC-5: API surfaces current state for every registered source
- **Given** one or more jobs have run at least once
- **When** `GET /api/status/sources` is called
- **Then** it returns one entry per job currently registered in `start_scheduler()`, each including: source id/name, status, last success time, last error message (if applicable), item count (if available), and the job's expected cadence (from its `IntervalTrigger`) so staleness can be judged relative to that source's own schedule, not a fixed global threshold

### AC-6: Never-run source doesn't error, shows a distinct "no data yet" state
- **Given** the app has just been deployed and a registered job hasn't fired yet (e.g. a 24h-cadence job right after deploy)
- **When** `GET /api/status/sources` is called before that job's first run
- **Then** that source appears with a distinct "not yet run" state (not a false "failure" and not omitted from the list) — no 500, no crash

### AC-7: Frontend shows per-source freshness and flags stale/failing sources
- **Given** `GET /api/status/sources` data is available
- **When** the "Data Sources" panel renders on `StatusPage.tsx`
- **Then** each source shows a human-relative last-updated time (e.g. "3h ago"), and is visually flagged when either (a) `status=failure` on the latest run, or (b) time since last success exceeds that source's own expected cadence — sources within cadence and last-successful show no warning

### AC-8: Frontend surfaces the last error for a failing source
- **Given** a source's latest run has `status=failure` with an error message
- **When** the panel renders that source
- **Then** the error message (or a truncated/sanitized version) is visible to the user without needing to check server logs

## Data Quality / Edge Cases
- **Job coverage scope**: only jobs actually registered via `scheduler.add_job(...)` inside `start_scheduler()` are instrumented. `refresh_breakout` is defined in `scheduler.py` but is not currently registered there (appears to be on-demand only, via `/api/trends/breakout`) — confirm this during implementation and exclude it from `SourceRun` tracking unless it's actually wired into the scheduler.
- **Granularity for `refresh_all`**: this function loops over multiple trends internally with its own per-trend try/except (existing isolation). Record success/failure at the level of the whole `refresh_all` invocation completing — not per inner trend. A partial-success run (some trends failed, overall function completed) should record as `success` for the outer job, consistent with how the function itself treats it today (logs a warning per trend, doesn't raise).
- **First deploy / empty table**: `GET /api/status/sources` must return the full list of registered sources even with zero `SourceRun` rows in the table (see AC-6) — not an empty list.
- **Malformed/missing item counts**: several `refresh_*` functions don't currently return a count (e.g. `refresh_climate` logs it but doesn't return; `refresh_faa` has no `db` session at all). Item count on `SourceRun` should be nullable — don't force every job to be refactored to return a count just to satisfy this feature.
- **`refresh_faa`** has no DB session in its current form (see `scheduler.py`) — confirm during implementation how it gets access to record a `SourceRun` (likely needs its own short-lived session, mirroring the others, since recording requires a DB write).

## Out of Scope
- Concurrent/parallelized startup refresh (separate follow-up per feature plan).
- Alerting/notifications on failure (v1 is passive visibility only).
- Historical run history or charting — only the latest run per source is tracked (upsert, not log).
- Retry/backoff changes to the underlying jobs.

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
