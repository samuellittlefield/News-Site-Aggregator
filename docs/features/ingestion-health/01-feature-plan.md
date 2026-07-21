# Feature Plan: Per-Source Ingestion Health Tracking

**Slug:** `ingestion-health` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-21

## Problem / Goal
The scheduler runs ~20 jobs (`votehub`, `house_polls`, `fec_candidates`, `kalshi`, `nws_alerts`, etc.), each wrapped in its own try/except so one bad upstream can't starve the others. That isolation is good for uptime but bad for transparency: when a source silently fails (upstream API changes shape, times out, gets rate-limited), the only trace is a log line on Railway. The frontend just keeps showing whatever was last successfully ingested, with no signal to the user that it might be hours or days stale. Goal: track the outcome of every scheduled ingestion run and surface it as a per-source freshness/health view, so users can tell "is this data current and trustworthy" instead of assuming it is.

## Context
- Cross-cutting infrastructure — touches the scheduler and every domain in `SOURCES.md`, not one vertical.
- Related existing surface: `/api/status` (`ServiceStatus` model, `service_status.py`, `StatusPage.tsx`) already exists but tracks *third-party infra* uptime (GitHub, OpenAI, Cloudflare, etc. via public statuspage.io feeds) — a completely different concern from "did our own ingestion job succeed." This feature adds a sibling data source (our own jobs), not a change to that one.
- Why now: this is the top item in the "Next" tier of the roadmap, and delivers direct user-facing value (data recency/trust signal) versus the auth item queued behind it, which is security hygiene.

## Scope
- [x] New data model: `SourceRun` (`backend/app/models.py`) — one row per scheduler job invocation: job id, status (success/failure), started_at, finished_at, item count, error message. Alembic migration required (prod already has Alembic wired up post `alembic-migrations`).
- [x] New backend service: a small helper (`backend/app/services/source_run.py` or similar) that wraps a job's execution and records the outcome — called from within each `refresh_*` function in `scheduler.py`, not a new job of its own.
- [x] Changed: every `refresh_*` function in `backend/app/scheduler.py` (~15-20 functions) gets instrumented to record a `SourceRun` row on both the success and failure paths, without changing the existing failure-isolation behavior (the outer try/except stays; recording happens in both branches).
- [x] New API route: extend `backend/app/routers/status.py` (or a new `ingestion.py` router, TBD in implementation plan) with `GET /api/status/sources` returning latest run + basic recency per source.
- [x] New frontend section: a "Data Sources" panel added to the existing `StatusPage.tsx` (alongside `ServiceStatusSection`), showing per-source last-success time, staleness (e.g. "updated 3h ago" vs a red flag if stale beyond expected cadence), and last error if failing.

## Non-Goals
- Concurrent/parallelized startup refresh — the roadmap item bundles "make startup refresh concurrent" with this, but that's a performance change orthogonal to health *tracking*. Defer to a follow-up unless Samuel wants it folded in.
- Alerting (email/Slack/push on failure) — v1 is passive visibility only, no notifications.
- Historical run history/charting beyond "most recent run per source" — v1 is current-state only, not a run-history table in the UI.
- Retry/backoff logic changes to the jobs themselves.

## Proposed Approach
Add a `SourceRun` model keyed by a stable `source_id` (matching job ids already used in `scheduler.add_job(..., id="votehub_job", ...)`), storing outcome + timestamp + optional item count + optional error string. Rather than a new scheduler job, wrap the existing `refresh_*` functions' bodies (or wrap at the `db_session` boundary they all share) so a run gets recorded whether it succeeds or raises — using an upsert-by-source_id (one current-state row per source, not an ever-growing log) to keep this v1 simple and avoid a new table growing unbounded. Expose it via a new endpoint, model it in the frontend the same way `ServiceStatus` is modeled today (fetch once, poll like `ServiceStatusSection` already does), and add expected-cadence data (already known per-source from `scheduler.py`'s `IntervalTrigger` values) so "3h ago" can be flagged red only when it exceeds that source's own cadence, not a fixed global threshold.

## Open Questions / Risks
- Upsert-by-source_id (current state only) vs. append-only log: recommend upsert for v1 per Non-Goals above — flag this explicitly in acceptance criteria so it's a deliberate choice, not an oversight.
- Where to hang the wrapping logic without touching all ~20 functions identically wrong — a shared context-manager/decorator used inside each `refresh_*` is probably cleaner than repeating boilerplate in each. Implementation plan should settle this.
- Does not change the existing "one bad source can't starve the rest" isolation — recording a failed run must never itself raise and break that isolation (recording errors should be caught and logged, not propagated).
- No dependency on other in-flight work; can start immediately.

## References
- Existing pattern: `backend/app/services/service_status.py` + `backend/app/routers/status.py` (third-party status, prior art for the "poll → model → route → UI section" shape, though a different data source).
- `backend/app/scheduler.py` — full list of jobs this instruments.
- `docs/ROADMAP.md` item #4.
