# Implementation Plan: Split the Scheduler into Two Job Groups

**Slug:** `scheduler-split` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

Grow `SOURCE_CADENCE` into a full job registry (id → label, cadence, callable,
domain, flags), derive all three job enumerations from it, then gate registration
by domain. The consolidation is the substance; the split falls out of it in a few
lines. Also splits `/api/refresh` into a cheap public path and an admin-gated
elections path with an in-flight guard.

**Depends on `elections-seam` (T1) being merged** — job domain is read off where the
service already lives.

## Backend Changes

*(Keep `Optional[...]` over `X | Y`.)*

| File | Change |
|---|---|
| `app/shared/services/source_run.py` | `SourceMeta` NamedTuple grows fields; `SOURCE_CADENCE` becomes `JOB_REGISTRY`; add `jobs_for(groups, flag)` helper |
| `app/scheduler.py` | `start_scheduler()` loops the registry instead of 17 literal `add_job` calls; job functions register themselves into the registry |
| `app/main.py` | `_startup_refresh()` and `_do_full_refresh()` derive from the registry; `/api/refresh` narrows to monitor; new admin-gated elections refresh route |
| `app/auth.py` | Unchanged — reuse `require_admin_key` as-is |
| `backend/.env.example` | Add `SCHEDULER_GROUPS` (AC-13) |
| `backend/tests/test_source_run.py` | Extend TC-7 into the three-way drift test (AC-11) |
| `backend/tests/test_scheduler_groups.py` | **New.** Group gating, precedence, fail-loud (AC-2/3/4) |
| `backend/tests/test_refresh_routes.py` | **New.** Public vs. admin-gated refresh, in-flight guard (AC-6/7/8) |

### The registry

```python
class JobMeta(NamedTuple):
    label: str
    cadence_minutes: int          # 0 == not scheduled
    domain: str                   # "elections" | "monitor" | "shared"
    fn: Optional[Callable] = None
    scheduled: bool = True
    on_startup: bool = True
    on_manual_refresh: bool = True
    startup_timeout: float = 120.0
    note: Optional[str] = None    # why a flag is False (AC-12)
```

Domains, from the T1 layout:

- **elections (5):** `house_polls_job`, `candidates_job`, `retirements_job`,
  `issue_tagger_job`, `economist_job`, plus `votehub_job`, `markets_job`,
  `kalshi_job` — **8 total**
- **monitor (8):** `refresh_job`, `extended_job`, `climate_job`, `news_job`,
  `weather_job`, `nws_alerts_job`, `earthquakes_job`, `faa_job`
- **shared (1):** `status_job`

Flags that encode today's deliberate choices explicitly (AC-12):

- `issue_tagger_job` — `on_manual_refresh=False`, `on_startup=False`,
  note: "weekly; up to 50 Groq LLM calls per run"
- `candidates_job` — `startup_timeout=600.0`, note: "~50-60 paginated FEC calls"
- `refresh_breakout` — a registry entry with `scheduled=False`,
  note: "on-demand only via /api/trends/breakout"

Carry over every existing `_startup_refresh` timeout budget verbatim (AC-5) — those
numbers were tuned, don't round them.

### Circular import

`source_run.py` must not import `scheduler.py`. Resolve with a decorator in
`scheduler.py` that registers each function into the registry at import time:

```python
@job("house_polls_job")
async def refresh_house_polls(): ...
```

The registry holds `fn=None` until `scheduler` is imported. `jobs_for()` raises if
asked for a job whose `fn` is still `None`, so a missing registration fails loudly
rather than silently skipping a source.

### Group gating

`SCHEDULER_GROUPS`, comma-separated, default `elections,monitor` (shared always
registers). Parse at `start_scheduler()` entry. **An empty value or an
unrecognized group raises at startup** (AC-14 in spirit — a scheduler that quietly
runs zero jobs is the silent-zero failure this project has already been bitten by
twice). `DISABLE_SCHEDULER=1` is checked first in `main.py`'s lifespan and keeps
precedence (AC-4).

### Refresh routes

- `POST /api/refresh` — public, unchanged 60s cooldown and 429. Now runs
  `jobs_for(["monitor","shared"], "on_manual_refresh")`. Response gains
  `"domains": ["monitor"]` and a count, so it stops implying it refreshed
  everything (AC-6).
- `POST /api/refresh/elections` — **new**, `require_admin_key` dependency,
  `jobs_for(["elections"], "on_manual_refresh")`. Returns 401 without a valid
  `X-Admin-Key` (AC-7).
- **In-flight guard (AC-8):** a module-level `asyncio.Lock` or an
  `_elections_refresh_running` bool. A second request while one is running returns
  **409 Conflict**, not a queue and not a 429 — the problem is overlap, not
  frequency. Release in a `finally`.

Per-job try/except and `SourceRun` recording stay exactly where they are, inside
each `refresh_*` (AC-9, AC-10). This ticket changes which jobs run and where the
list comes from, never how a job behaves when its upstream misbehaves.

## Frontend Changes

**None required.** `TrendsPage`'s Refresh button keeps working against the same
endpoint. The richer response body is additive.

Optional, if it's cheap: surface `domains` from the response in the button's toast
so the UI stops implying a full refresh. If it costs more than a few lines, defer
to T3 — it owns the polling app's own refresh control.

## Data Model / Migration Notes

**No schema change, no migration.** `SourceRun` rows, columns and upsert keys are
untouched. The registry is in-process configuration.

One behavioural note worth expecting: running with `SCHEDULER_GROUPS=monitor`
leaves election `SourceRun` rows frozen at their last run. They will look stale on
the Data Sources panel because they *are* stale — AC-3 asks that the panel reflect
"not running here" rather than "failing", so decide whether that's a
registry-derived filter on `/api/status/sources` or a status value. Registry-derived
is cleaner; don't add a column for it.

## Sequencing

Each step keeps the suite green.

1. **Extend `SourceMeta` → `JobMeta`** with domain and flags, still 17 entries, no
   consumers changed. Suite green.
2. **Add the `@job` decorator** and register all 17 functions. Registry now holds
   callables; nothing reads them yet.
3. **Rewrite `start_scheduler()`** to loop the registry. Assert the same 17 ids and
   cadences register. Suite green.
4. **Rewrite `_startup_refresh()`** from the registry, preserving timeouts. This
   closes the `refresh_climate` gap.
5. **Rewrite `_do_full_refresh()`** from the registry, monitor-only, and add the
   `domains` field to the response.
6. **Add `POST /api/refresh/elections`** with `require_admin_key` and the in-flight
   guard.
7. **Add group gating** and the fail-loud parse.
8. **Extend the drift test** to all three enumerations; add the two new test
   modules.

Steps 1–3 are the consolidation and carry most of the risk. If time runs short,
1–5 alone are worth shipping — they fix the live `/api/refresh` bug without the
split.

## Documentation Updates

- [ ] `SOURCES.md` — add a line to the ingestion-health note that jobs now carry a
      domain and can be gated by group.
- [ ] `.env.example` — `SCHEDULER_GROUPS` with accepted values and default (AC-13).
- [ ] `CLAUDE.md` — one line: new scheduled sources register via `@job` in the
      registry, not by hand in three places.
- [ ] `docs/ROADMAP.md` — T2 → shipped with PR link.

## Risks / Rollback

- **Rollback is `git revert`** — no migration, no data change. `SCHEDULER_GROUPS`
  unset already means today's behaviour, so the split is inert until used.
- **Highest risk: a job silently stops running.** Worse than a crash, because
  `SourceRun` would just stop updating and the panel would read stale. The step-3
  assertion that the same 17 ids register with the same cadences is the guard, and
  it should be a real test, not a manual check.
- **Circular import** between `source_run` and `scheduler`. Step 2 is where this
  surfaces; the decorator pattern above is the intended shape.
- **`/api/refresh` is user-visible.** Its behaviour genuinely changes — it stops
  pretending to refresh elections data. That's the fix, not a regression, but it
  should be called out in the PR so it doesn't read as a surprise later.
- **Test-suite coupling:** `conftest.py` sets `DISABLE_SCHEDULER=1` at import. AC-4
  must hold or the whole suite changes behaviour. Verify early, not at step 7.

## Test Plan Pointer

See `04-test-cases.md` for the cases this implementation must satisfy.
