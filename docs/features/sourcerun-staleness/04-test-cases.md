# Test Cases: Quiet-Source Detection on `SourceRun`

**Slug:** `sourcerun-staleness` &nbsp; **Source:** `02-acceptance-criteria.md`

## Coverage Map

| AC | Test IDs |
|---|---|
| AC-1 Productive run recorded | TC-1 |
| AC-2 Empty run not recorded | **TC-2** |
| AC-3 Every source declares | TC-3 |
| AC-4 `data_state` computed | TC-5 |
| AC-5 quiet | **TC-4** |
| AC-6 Exemptions hold | TC-6 |
| AC-7 NULL reads unknown | **TC-7** |
| AC-8 Validated on real incidents | **TC-8, TC-9** |
| AC-9 votehub count | TC-10 |
| AC-10 Additive, frontend untouched | TC-11, TC-12 |
| AC-11 Migration | TC-13 |

## Backend

### TC-1 — Productive run sets the timestamp (covers AC-1)
`record_success` with `item_count=4`. **Expected:** `last_nonempty_at` set to now; `last_run_at` and `last_success_at` also set.

### TC-2 — Empty run preserves the timestamp (covers AC-2)
Seed `last_nonempty_at` three days ago. Call `record_success` with `item_count=0`, then again with `None`.
**Expected:** `last_run_at`/`last_success_at` advance both times; `last_nonempty_at` stays three days old. **This is the whole mechanism** — if it advances on zero, nothing else works.

### TC-3 — Registry completeness (covers AC-3)
Walk the registry. **Expected:** every entry has `expected_data_interval_minutes` as a positive int or an explicit `None`, and the test fails if a new source is added without one.

### TC-6 — Exempt source is never quiet (covers AC-6)
`issue_tagger_job` (`None`) with `last_nonempty_at` 60 days old. **Expected:** `data_state: "exempt"`.

### TC-8 — Would it have caught Economist? (covers AC-8)
Replay the real timeline: productive 2026-08-02, then `success`/`item_count: 0` every 12h.
**Expected:** `data_state: "quiet"` no later than ~16 days in. **If it is still `ok` at 46 days, the expectation value is wrong — retune before merge, do not adjust this test.**

### TC-9 — Would it have caught Kalshi? (covers AC-8)
Replay: productive at `item_count: 4`, then a run at 0.
**Expected:** `quiet` within hours, given a 10-minute cadence and a 1-hour expectation.

### TC-10 — votehub counts everything (covers AC-9)
Mock a run storing approval + generic ballot but no new House district polls.
**Expected:** `item_count > 0`. Today it records 0 because only the House slice is counted.

### TC-11 — Response additive (covers AC-10)
Diff `/api/status/sources` against a pre-change fixture. **Expected:** every existing field identical in name, type and value; only additions.

### TC-13 — Migration round-trips (covers AC-11)
`upgrade head` → `downgrade` → `upgrade head`. **Expected:** all clean, and T1's autogenerate check reports an empty diff.

### TC-14 — Failure preserves productivity history
Productive run, then a failing run. **Expected:** `last_nonempty_at` survives, the same way `last_success_at` already does.

### TC-15 — Recording stays defensive
Force a DB error during recording. **Expected:** swallowed and logged, never raised into the ingestion job (PR #9 AC-3 preserved).

### TC-4 — `data_state` is `quiet` (covers AC-5)
Ran 5 minutes ago, succeeded, `last_nonempty_at` 30 days old, expectation 14 days. **Expected:** `data_state: "quiet"`.

### TC-5 — `data_state` is `producing` when healthy (covers AC-4)
Recent successful run with `last_nonempty_at` inside the expectation. **Expected:** `producing`.

### TC-7 — NULL history reads `unknown` (covers AC-7)
`last_nonempty_at` NULL, everything else healthy — all 17 sources immediately after migration.
**Expected:** `data_state: "unknown"`, never `quiet`. **Verify against a freshly migrated database, not just a fixture.**

### TC-12 — The panel is unchanged (covers AC-10)
`npm run dev`, Admin page.
**Expected:** the Data Sources panel renders exactly as before — same states, same badges, same banner counts. `classify()` and `SourceHealthSection` must show no diff.

## Edge Cases & Failure Modes

- **Upstream down/malformed:** unchanged — this ticket adds no upstream calls.
- **First run / empty table:** TC-7 is the first-run case.
- **Re-run:** one upserted row per `source_id`, never an append log.
- **Rate limit / auth:** none.
- **Clock:** all comparisons tz-aware UTC; confirm nothing goes negative across a DST boundary in the frontend's `minutesSince`.

## Regression Check

- `/api/status/sources` — all 17 sources, existing fields untouched
- Admin page Data Sources panel and its summary banner
- A full scheduled cycle — each job still records its own row
- `docs/features/ingestion-health/` TC-7, the registry drift test, still passes
- Full suite green

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
