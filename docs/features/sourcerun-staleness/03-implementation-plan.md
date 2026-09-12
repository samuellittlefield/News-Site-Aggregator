# Implementation Plan: Quiet-Source Detection on `SourceRun`

**Slug:** `sourcerun-staleness` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

One nullable column, one per-source expectation in the registry, one new state in the
shared classifier, and a fix to `votehub_job`'s item count. No `fetch_*` behaviour
changes.

## Backend Changes

*(Keep `Optional[...]` over `X | Y`.)*

| File | Change |
|---|---|
| `app/models/shared.py` | `SourceRun.last_nonempty_at` — nullable `DateTime(timezone=True)` |
| `backend/alembic/versions/` | Additive migration for the above |
| `app/shared/services/source_run.py` | `SourceMeta` gains `expected_data_interval_minutes: Optional[int]`; `record_success` sets `last_nonempty_at` only when `item_count > 0`; `record_failure` leaves it alone |
| `app/shared/routers/status.py` | Expose `last_nonempty_at` and `expected_data_interval_minutes`, and compute `data_state` (AC-4-AC-7) |
| `app/scheduler.py` | `refresh_votehub` records the full count (AC-10). No other job touched |
| `SOURCES.md` | Note the quiet state and what the exemptions mean |

**`record_success` is the delicate part.** It already swallows its own exceptions so a
recording failure cannot break the ingestion job it was recording (PR #9 AC-3). Keep the
new assignment inside that same try block.

## Frontend Changes

**None.** Rescoped 2026-09-12 — `classify()`, `SourceHealthSection` and
`summarizeSourceHealth()` are not touched, and the panel renders exactly as today (AC-10).
The verdict is computed on the route instead, so a panel, a digest or an alert can consume
`data_state` later without reimplementing the rule.

`src/api/client.ts`'s `SourceRun` type may optionally gain the new fields for future use,
but nothing must read them yet.

## Data Model / Migration Notes

- Additive nullable column. No backfill: NULL means not-yet-known and populates on the
  next productive run (AC-7).
- Run T1's autogenerate-drift check after, to confirm the model and migration agree.
- Downgrade should drop the column cleanly (AC-12).

## Sequencing

1. Model + migration. `upgrade`, `downgrade`, `upgrade` again.
2. `record_success` / `record_failure` (AC-1, AC-2) and the registry field (AC-3).
3. **Tune the expectation values against the real incident timelines (AC-8) before
   building anything on top of them.** If Economist would not have been caught early, the numbers
   are wrong and everything downstream is built on sand.
4. `refresh_votehub` item count (AC-10).
5. Route fields plus the `data_state` computation (AC-4-AC-7, AC-10).
6. `SOURCES.md`.

## Documentation Updates

- [ ] `SOURCES.md` — the quiet state; why `issue_tagger_job` is exempt
- [ ] `.env.example` — nothing new
- [ ] `docs/ROADMAP.md` — #13 → shipped with the PR link

## Risks / Rollback

- **Rollback is `git revert` plus `alembic downgrade`.** The column is additive and
  unread by anything else.
- **The real risk is false positives.** A permanently yellow panel gets ignored, which
  recreates the exact problem this ticket exists to solve. Start generous, tighten later.
  AC-9 is the check that the numbers mean something.
- **Second risk: AC-7.** Getting NULL handling wrong makes all 17 sources read `quiet`
  immediately after deploy. Test against a freshly migrated database, not just in theory.
- **Do not widen scope into the panel.** The frontend is deliberately untouched (AC-10).
- **Do not let this ticket fix a source.** If Code notices another feed looking quiet
  while working here, that is a finding to report, not a fix to smuggle in.

## Test Plan Pointer

See `04-test-cases.md`.
