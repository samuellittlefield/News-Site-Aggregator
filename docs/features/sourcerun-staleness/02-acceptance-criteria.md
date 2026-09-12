# Acceptance Criteria: Quiet-Source Detection on `SourceRun` (backend only)

**Slug:** `sourcerun-staleness` &nbsp; **Source:** `01-feature-plan.md` (rev 2)

## Criteria

### AC-1: A productive run is recorded
- **Given** a job that succeeds with `item_count` greater than zero
- **When** `record_success` runs
- **Then** `last_nonempty_at` is set to now, alongside the existing `last_run_at` and `last_success_at`

### AC-2: An empty run is not recorded as productive
- **Given** a job that succeeds with `item_count` of 0 or `None`
- **When** `record_success` runs
- **Then** `last_run_at` and `last_success_at` update as they do today, and **`last_nonempty_at` is left untouched** — preserving how long it has been since real output

### AC-3: Every source declares an expectation or an exemption
- **Given** the registry
- **When** it is read
- **Then** every entry has `expected_data_interval_minutes` as a positive integer or an explicit `None`, and every `None` carries a comment saying why zero is legitimate for that source

### AC-4: The route computes `data_state`
- **Given** a source row
- **When** `GET /api/status/sources` is called
- **Then** each entry carries `data_state` of `producing`, `quiet`, `exempt` or `unknown`, computed server-side so every reader gets the same verdict without reimplementing the rule

### AC-5: `quiet` means ran fine but produced nothing for too long
- **Given** a source whose last run succeeded recently but whose `last_nonempty_at` is older than its expectation
- **Then** `data_state` is `quiet`

### AC-6: Exempt sources are never quiet
- **Given** a source with `expected_data_interval_minutes` of `None` — `issue_tagger_job` returning 0 with nothing pending
- **Then** `data_state` is `exempt`, regardless of how long since it produced

### AC-7: Unknown history is not a problem
- **Given** `last_nonempty_at` is NULL, as it will be for all 17 sources immediately after the migration
- **Then** `data_state` is `unknown`, never `quiet`. The column populates on the next productive run

### AC-8: The design is validated against the two real incidents
- **Given** the Economist timeline (productive 2026-08-02, then `success`/`item_count: 0` every 12h until 09-11) and the Kalshi timeline (productive at 4 items, then a run at 0)
- **When** those sequences are replayed
- **Then** Economist is `quiet` well before 46 days and Kalshi within hours. **If either stays `producing`, the expectation values are wrong and must be retuned before merge — do not adjust the test**

### AC-9: `votehub_job` counts everything it stored
- **Given** `refresh_votehub` currently records `item_count=house`, discarding `counts` from `fetch_votehub_polls`
- **Then** `item_count` reflects all rows the job upserted, so `items: 0` no longer appears while approval and generic-ballot data is being refreshed normally

### AC-10: The response is additive and the frontend is untouched
- **Given** `AdminPage`'s `useSourceRuns` is the only consumer
- **Then** every existing field keeps its name, type and meaning; `classify()`, `SourceHealthSection` and `summarizeSourceHealth()` are **not modified**; the panel renders exactly as it does today

### AC-11: The migration is clean and reversible
- **Given** an additive nullable column on `SourceRun`
- **When** `alembic upgrade head` then `downgrade` then `upgrade` run
- **Then** all succeed, and T1's autogenerate-drift check reports an empty diff afterwards

## Data Quality / Edge Cases

- **A source that fails then recovers:** `record_failure` must not clear `last_nonempty_at`, exactly as it already preserves `last_success_at`.
- **Recording stays defensive.** `record_success`/`record_failure` swallow their own DB errors by design (PR #9 AC-3). The new assignment goes inside that same try block and must not introduce a path that raises into an ingestion job.
- **Idempotency:** still one upserted row per `source_id`, never an append-only log.
- **Clock:** tz-aware UTC throughout, consistent with the existing columns.
- **Failure isolation unchanged** — no `fetch_*` behaviour changes.

## Out of Scope

- Alerting, email, push — deferred; zero traffic makes it heavy-handed
- Any frontend change, including a `quiet` badge
- Gating the endpoint — that is roadmap #16, a launch blocker in its own right
- Tracking the freshness of the data's own timestamps (poll fieldwork dates etc.)
- Fixing any individual source, including #15
- Deciding where `SourceRun` lives after the extraction (T6)

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
