# Acceptance Criteria: Split the Scheduler into Two Job Groups

**Slug:** `scheduler-split` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: One registry is the only place jobs are enumerated
- **Given** four hand-maintained enumerations today (`SOURCE_CADENCE` 17, `start_scheduler` 17, `_startup_refresh` 15, `_do_full_refresh` 12)
- **When** the refactor is complete
- **Then** a single registry in `app/shared/services/source_run.py` holds every job's id, label, callable, cadence, domain and flags, and no other hand-written list of jobs exists in the codebase

### AC-2: Default scheduler behaviour is unchanged
- **Given** no `SCHEDULER_GROUPS` env var set
- **When** the app starts
- **Then** the same 17 job ids register with exactly the same cadences as before this ticket — no job added, removed, or retimed

### AC-3: Job groups can be enabled independently
- **Given** `SCHEDULER_GROUPS=monitor`
- **When** the app starts
- **Then** only monitor-domain and shared jobs register; no elections job is registered, and `GET /api/status/sources` reflects that rather than reporting the missing jobs as failing

### AC-4: `DISABLE_SCHEDULER` still wins
- **Given** `DISABLE_SCHEDULER=1`, with or without `SCHEDULER_GROUPS` set
- **When** the app starts (including under `TestClient`)
- **Then** no jobs register and no startup refresh fires — current test-suite behaviour is preserved exactly

### AC-5: Startup refresh derives from the registry
- **Given** the registry with per-job startup timeout budgets
- **When** `_startup_refresh` runs
- **Then** it iterates the registry rather than a hand-written list, covers every job flagged for startup (closing today's gap where `refresh_climate` is omitted), and keeps each job's existing timeout budget and isolation via `_safe_refresh`

### AC-6: The public refresh button stays cheap, and says what it does
- **Given** `POST /api/refresh` with no admin key
- **When** it is called
- **Then** it runs only monitor-domain jobs flagged for manual refresh, keeps its existing 60s cooldown and 429 behaviour, and its response names which domains were refreshed so the caller isn't misled

### AC-7: Election jobs get an admin-gated refresh path
- **Given** a request to refresh election-domain jobs
- **When** it is sent without a valid `X-Admin-Key`
- **Then** it is rejected with 401 via the existing `require_admin_key`; **and when** sent with a valid key, the election-domain jobs run in the background

### AC-8: Concurrent elections refreshes cannot overlap
- **Given** an elections refresh already running
- **When** a second valid request arrives before it finishes
- **Then** the second is rejected rather than queued, so FEC paginations never compete — the failure `fec_candidates.py` warns about in comments

### AC-9: Failure isolation is unchanged
- **Given** one upstream source raising or timing out
- **When** any refresh path runs (scheduled, startup, manual, admin-gated)
- **Then** the remaining jobs in that run still execute and complete, exactly as today

### AC-10: `SourceRun` recording is unchanged
- **Given** a job that succeeds or fails
- **When** it runs through any path
- **Then** it records the same `SourceRun` row it does today — status, last run/success time, item count, last error, cadence — and recording failures remain defensively swallowed

### AC-11: Drift between enumerations is impossible to reintroduce
- **Given** the extended drift test (successor to `ingestion-health` TC-7)
- **When** the suite runs
- **Then** registered ids, startup-refresh ids and manual-refresh ids are each checked against the registry, and the test **fails** if a job is added to the registry without a domain or omitted from a path it should be in

### AC-12: Deliberate omissions are recorded, not implied
- **Given** `refresh_breakout` (never scheduled, on-demand only) and `run_issue_tagger` (weekly, expensive, excluded from manual refresh)
- **When** the registry is read
- **Then** each carries an explicit flag and a comment stating why, so neither reads as an accidental gap the way today's omissions do

### AC-13: New configuration is documented
- **Given** the new `SCHEDULER_GROUPS` variable
- **When** the ticket is complete
- **Then** it appears in `backend/.env.example` with its accepted values and default, per repo convention

## Data Quality / Edge Cases

- **Upstream unavailable:** unchanged from today — per-job try/except keeps one bad source
  from starving the rest (AC-9). This ticket must not alter any `fetch_*` body.
- **Idempotency:** unchanged. No model or upsert logic is touched, so re-running any job
  still upserts rather than duplicating.
- **Rate limits:** the reason for AC-6/AC-7/AC-8. FEC is ~50-60 paginated calls per run
  against a 1,000/hour key limit; a 60s cooldown on a public endpoint permits 60 triggers
  an hour. The gating and the in-flight guard are what keep that in bounds.
- **Auth failure:** a missing or wrong `ADMIN_API_KEY` must fail closed (401), consistent
  with `write-endpoint-auth` (PR #10).
- **Empty group:** `SCHEDULER_GROUPS=` or an unrecognized value should fail loudly at
  startup rather than silently registering nothing — a scheduler that quietly runs zero
  jobs is exactly the silent-zero failure this project has been bitten by twice.

## Out of Scope

- Two processes or two deploy targets (T5b)
- Any cadence change to any existing job
- Adding `refresh_breakout` to the schedule
- Fixing any individual source, including the Economist scraper (roadmap item #10)
- Changing `DISABLE_SCHEDULER` semantics
- Frontend changes to the Refresh button beyond what AC-6's honest response enables (T3 owns the polling app's own control)

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
