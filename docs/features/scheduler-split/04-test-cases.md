# Test Cases: Split the Scheduler into Two Job Groups

**Slug:** `scheduler-split` &nbsp; **Source:** `02-acceptance-criteria.md`

Automatable against the existing pytest harness. New modules:
`backend/tests/test_scheduler_groups.py` and `backend/tests/test_refresh_routes.py`;
the drift cases extend `backend/tests/test_source_run.py`.

## Coverage Map

| AC | Test IDs |
|---|---|
| AC-1 One registry | TC-1, TC-2 |
| AC-2 Default unchanged | TC-3 |
| AC-3 Groups independent | TC-4, TC-5, TC-6 |
| AC-4 `DISABLE_SCHEDULER` wins | TC-7 |
| AC-5 Startup from registry | TC-8, TC-9 |
| AC-6 Public refresh cheap + honest | TC-10, TC-11 |
| AC-7 Admin-gated elections refresh | TC-12, TC-13 |
| AC-8 No overlap | TC-14 |
| AC-9 Failure isolation | TC-15 |
| AC-10 `SourceRun` unchanged | TC-16 |
| AC-11 Drift impossible | TC-17, **TC-18** |
| AC-12 Omissions explicit | TC-19 |
| AC-13 Config documented | TC-20 |
| Fail-loud config | TC-21 |

## Backend

### TC-1 — Registry is complete (covers AC-1)
- **Type:** unit
- **Steps:** import `JOB_REGISTRY`; inspect every entry.
- **Expected:** 18 entries (17 scheduled + `refresh_breakout` with
  `scheduled=False`); every entry has a non-empty `label`, a `domain` in
  `{elections, monitor, shared}`, and a non-`None` `fn` once `scheduler` is imported.

### TC-2 — No second job list survives (covers AC-1)
- **Type:** unit
- **Steps:** AST-scan `app/main.py` and `app/scheduler.py` for list/tuple literals of
  three or more `refresh_*` references.
- **Expected:** none found. This is the case that stops the four-lists problem from
  quietly becoming five.

### TC-3 — Default registration matches today exactly (covers AC-2)
- **Type:** unit
- **Setup:** `SCHEDULER_GROUPS` unset.
- **Steps:** call `start_scheduler()` with a stub; collect `(id, interval)` pairs.
- **Expected:** the same 17 ids with the same intervals as before this ticket —
  compare against a committed baseline, not against the registry itself, or the test
  proves only that the code agrees with itself.

### TC-4 — Monitor-only registration (covers AC-3)
- **Type:** unit
- **Setup:** `SCHEDULER_GROUPS=monitor`.
- **Steps:** call `start_scheduler()` with a stub.
- **Expected:** 8 monitor jobs + `status_job` register; none of the 8 elections jobs
  (`house_polls_job`, `candidates_job`, `retirements_job`, `issue_tagger_job`,
  `economist_job`, `votehub_job`, `markets_job`, `kalshi_job`) do.

### TC-5 — Elections-only registration (covers AC-3)
- **Type:** unit
- **Setup:** `SCHEDULER_GROUPS=elections`.
- **Expected:** the 8 elections jobs + `status_job` register; no monitor job does.

### TC-6 — Status panel distinguishes "not running here" from "failing" (covers AC-3)
- **Type:** integration
- **Setup:** `SCHEDULER_GROUPS=monitor`, with existing elections `SourceRun` rows in
  the DB from a prior run.
- **Steps:** `GET /api/status/sources`.
- **Expected:** elections sources are not reported as failing or stale-and-broken.
  They are either omitted or marked as not-registered-in-this-process. A source the
  operator deliberately turned off must not read as an incident.

### TC-7 — `DISABLE_SCHEDULER` beats groups (covers AC-4)
- **Type:** integration
- **Setup:** `DISABLE_SCHEDULER=1` **and** `SCHEDULER_GROUPS=elections,monitor`.
- **Steps:** start under `TestClient`.
- **Expected:** zero jobs register, no startup refresh fires. Verify early in
  implementation — `conftest.py` sets this at import, so the entire suite depends on it.

### TC-8 — Startup refresh covers every flagged job (covers AC-5)
- **Type:** unit
- **Setup:** patch all refresh functions.
- **Steps:** run `_startup_refresh()`; record call order.
- **Expected:** every registry entry with `on_startup=True` is called, **including
  `refresh_climate`**, which today's hand-written list omits. `run_issue_tagger` is
  not called.

### TC-9 — Startup timeout budgets are preserved (covers AC-5)
- **Type:** unit
- **Steps:** assert each entry's `startup_timeout` against the values currently in
  `main.py`.
- **Expected:** exact match, notably `candidates_job` at 600.0 and the 180.0 entries
  (`refresh_all`, `extended_sources`, `news`, `house_polls`, `economist`). These were
  tuned; a rounded value is a regression.

### TC-10 — Public refresh runs monitor jobs only, and says so (covers AC-6)
- **Type:** integration
- **Steps:** `POST /api/refresh` with no admin key; patch refresh functions.
- **Expected:** 200; only monitor + shared jobs flagged `on_manual_refresh` are
  invoked; **no elections job runs**; the response body names the domains refreshed.
  Fixes today's bug where the button silently skips all polling data.

### TC-11 — Public refresh cooldown is unchanged (covers AC-6)
- **Type:** integration
- **Steps:** `POST /api/refresh` twice within 60s.
- **Expected:** 200 then 429, with the existing retry-seconds message. Unchanged
  from `write-endpoint-auth` (PR #10).

### TC-12 — Elections refresh rejects without a key (covers AC-7)
- **Type:** integration
- **Steps:** `POST /api/refresh/elections` with (a) no header, (b) a wrong key,
  (c) `ADMIN_API_KEY` unset in the environment.
- **Expected:** 401 in all three. Case (c) is the fail-closed check.

### TC-13 — Elections refresh runs with a valid key (covers AC-7)
- **Type:** integration
- **Steps:** `POST /api/refresh/elections` with a valid `X-Admin-Key`; patch refresh
  functions.
- **Expected:** 200; the 8 elections jobs flagged `on_manual_refresh` are invoked;
  `run_issue_tagger` is **not**; no monitor job runs.

### TC-14 — Concurrent elections refresh is rejected, not queued (covers AC-8)
- **Type:** integration
- **Setup:** patch one elections refresh to block on an event.
- **Steps:** fire a valid request, then a second while the first is still running;
  release the event.
- **Expected:** second returns **409**, not 429 and not a queued 200. The first
  completes normally. Afterwards a third request succeeds, proving the guard is
  released in a `finally` and can't wedge the endpoint permanently.

### TC-15 — One failing job doesn't starve the rest (covers AC-9)
- **Type:** integration
- **Steps:** patch one job to raise and another to time out; run each path in turn —
  scheduled, startup, public refresh, admin refresh.
- **Expected:** the remaining jobs in that run still execute and complete, on every
  path. Identical to today's behaviour.

### TC-16 — `SourceRun` recording is unchanged (covers AC-10)
- **Type:** integration
- **Steps:** run one succeeding and one failing job; inspect the rows.
- **Expected:** same upsert semantics — success sets `last_run_at` and
  `last_success_at`; failure sets `last_run_at` and `error_message` while
  **preserving** `last_success_at`. A DB error during recording is still swallowed
  and logged, never propagated.

### TC-17 — Three-way drift check (covers AC-11)
- **Type:** unit (extends `ingestion-health` TC-7)
- **Steps:** compare registered ids, startup-refresh ids and manual-refresh ids
  against the registry.
- **Expected:** each set equals the registry filtered by its flag. No id appears in a
  path it isn't flagged for, and none is missing from one it is.

### TC-18 — Drift check FAILS on a bad registry entry (covers AC-11)
- **Type:** unit (negative)
- **Steps:** add a registry entry with no `domain`; run the drift test. Then add one
  with a domain but no registered `fn`; run again. Revert both.
- **Expected:** **fails both times**, naming the offending id. Same reasoning as the
  boundary test in T1 — a guard that can't fail isn't a guard.

### TC-19 — Deliberate omissions carry a reason (covers AC-12)
- **Type:** unit
- **Steps:** inspect the `refresh_breakout`, `issue_tagger_job` and `candidates_job`
  entries.
- **Expected:** `refresh_breakout` has `scheduled=False`; `issue_tagger_job` has
  `on_manual_refresh=False` and `on_startup=False`; each has a non-empty `note`. The
  point is that a future reader can tell a decision from an oversight — which is
  exactly what today's `/api/refresh` omission failed to do.

### TC-20 — New config is documented (covers AC-13)
- **Type:** unit
- **Steps:** read `backend/.env.example`.
- **Expected:** contains `SCHEDULER_GROUPS` with accepted values and the default.

### TC-21 — Bad group config fails loudly at startup
- **Type:** integration
- **Steps:** start with (a) `SCHEDULER_GROUPS=` empty, (b) `SCHEDULER_GROUPS=nonsense`.
- **Expected:** startup raises with a message naming the bad value and the valid
  options. It must **not** start with zero jobs registered — a scheduler quietly
  running nothing is the silent-zero failure this project has hit twice.

## Frontend

### TC-22 — Refresh button still works (manual)
- **Type:** manual
- **Steps:** `npm run dev`; open Trends; click Refresh; watch the network tab.
- **Expected:** 200 with the new response shape; no console error; a second click
  inside 60s shows the existing cooldown behaviour. The richer body is additive, so
  the button must not need a frontend change to keep working.
- **Automation note:** would live in `frontend/src/**/*.test.tsx` once Vitest exists;
  none configured today.

## Edge Cases & Failure Modes

- **Upstream down/malformed:** unchanged — TC-15 across all four paths.
- **Empty DB / first run:** no model or upsert change; `SourceRun` rows are created
  on first record and upserted after (TC-16).
- **Rate limit / auth failure:** the reason for TC-12/13/14. FEC is ~50-60 paginated
  calls per run against a 1,000/hour key; gating plus the in-flight guard are what
  keep a public endpoint from exhausting it.
- **Registry/scheduler circular import:** surfaces at implementation step 2. TC-1's
  `fn is not None` assertion is the check that registration actually happened.

## Regression Check

- `GET /api/status/sources` and the Admin Data Sources panel — all 17 sources present
  and correctly classified with default config
- `POST /api/refresh` from the Trends page button — 200, then 429 within 60s
- Admin candidate issue-tag confirm/reject — still 401 without `X-Admin-Key`
  (shares `require_admin_key` with the new route)
- A full scheduled cycle on a local run — every job fires on its own cadence and
  records a `SourceRun` row
- Deploy check: `DISABLE_SCHEDULER` unset in production means both groups register,
  i.e. no behaviour change on Railway from this ticket alone

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
