# Implementation Plan: Draw the Backend Elections/Monitor Seam

**Slug:** `elections-seam` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

A pure move: 47 modules relocate from two flat directories into three bounded
packages, `models.py` becomes a package with one `Base`, and a new test enforces
the boundary. No function body changes, no route changes, no schema change. The
acceptance bar is an empty Alembic autogenerate diff (AC-5) and a green suite whose
only edits are import paths (AC-10).

## Backend Changes

*(Keep `Optional[...]` over `X | Y` — Samuel's local venv is still 3.9 even though
Railway and CI run 3.11.)*

### Target layout

| From | To |
|---|---|
| `app/routers/{candidates,economist,forecasts,markets,polls,votehub}.py` | `app/elections/routers/` |
| `app/services/{economist_yougov,fec_candidates,forecast_constants,forecast_model,house_polls,issue_tagger,kalshi,prediction_markets,retirements,votehub}.py` | `app/elections/services/` |
| `app/routers/{astronomy,climate,hazards,news,trends,weather}.py` | `app/monitor/routers/` |
| `app/services/{astronomy,climate,clustering,earthquakes,faa_status,gdelt,google_trends_multi,news,news_categories,nws_alerts,nyt,pageviews,pytrends_service,reddit_trending,regional_weather,situation_builder,summarizer,trends,velocity,wikipedia,wikipedia_trending}.py` | `app/monitor/services/` |
| `app/routers/status.py` | `app/shared/routers/` |
| `app/services/{service_status,source_run,topic_matcher}.py` | `app/shared/services/` |

Counts: routers 6 / 6 / 1, services 10 / 21 / 3. The old `app/routers/` and
`app/services/` directories are deleted entirely (AC-1) — no shims, no re-export
packages at the old paths.

### Files changed beyond the move

| File | Change |
|---|---|
| `app/models.py` | **Delete**, replaced by the package below |
| `app/models/base.py` | **New.** The single `Base = declarative_base()`, moved verbatim from `models.py` line 6 |
| `app/models/__init__.py` | **New.** Re-exports `Base` **and** all 25 classes, with an explicit `__all__`, so both `from app.models import HousePoll` (AC-4) and `alembic/env.py`'s `from app.models import Base` keep resolving |
| `app/models/elections.py` | **New.** `Candidate`, `CandidateIssueTag`, `HousePoll`, `CompetitiveDistrict`, `HouseRetirement`, `EconYouGovReport`, `EconYouGovCrosstab`, `VoteHubPoll`, `PredictionMarket`, `MarketSnapshot`, `GenericBallotAggregate` (11) |
| `app/models/monitor.py` | **New.** `TrendCluster`, `Trend`, `Article`, `Summary`, `TrendSnapshot`, `WikiPage`, `WikiPageView`, `NewsArticle`, `RegionalWeather`, `Earthquake`, `NWSAlert`, `ClimateEvent` (12) |
| `app/models/shared.py` | **New.** `ServiceStatus`, `SourceRun` (2) |
| `app/main.py` | 13 `from app.routers import X as X_router` lines repoint to the three packages. Router include order, startup refresh, `/api/refresh`, CORS and lifespan are **unchanged** (AC-2, AC-11) |
| `app/scheduler.py` | 33 service imports repoint. **Nothing else in this file changes** — same 17 `add_job` calls, same ids, same `IntervalTrigger` values (AC-9) |
| `app/auth.py`, `app/database.py` | Unchanged, stay at `app/` |
| `backend/tests/*.py` | Import paths only. No assertion, fixture or expected value changes (AC-10) |
| `backend/tests/test_module_boundaries.py` | **New.** The boundary test (AC-7) |
| `.github/workflows/ci.yml` | Add an autogenerate-drift step (AC-5) |

**Critical: `Base` is declared exactly once, in the new `app/models/base.py`, and all
three model modules import it from there.** Today it lives at `models.py` line 6
(`Base = declarative_base()`); `app/database.py` has no `Base` and must not grow one.
It cannot live in `app/models/__init__.py` either — the submodules would then import
from the package that imports them.

One `Base` means one `MetaData`, and `MetaData` is what Alembic diffs against the
database. If each new module called `declarative_base()` itself you would get three
separate registries, `env.py` would import one of them, and autogenerate would propose
dropping the two-thirds of the schema it could no longer see.

**`alembic/env.py` line 23 does `from app.models import Base`.** That import must keep
resolving after the split — it is the concrete form of the AC-6 check, and it is a
one-line failure if `__init__.py` re-exports only the model classes and forgets `Base`.

### The boundary test (AC-7)

`backend/tests/test_module_boundaries.py` walks every `.py` under `app/elections/`
and `app/monitor/` with `ast.parse`, collects `Import` / `ImportFrom` targets, and
asserts no `app.elections.*` module imports `app.monitor.*` or vice versa. Static
AST parsing, not importing — it must not execute module bodies. A second assertion
covers AC-8: nothing under `app/shared/` imports from either domain.

Include a commented-out deliberate violation in the test file's docstring showing
how to verify the test actually fails, since a boundary test that can't fail is
worthless.

### Autogenerate drift check (AC-5)

New CI step after the existing pytest run:

```
alembic upgrade head
alembic revision --autogenerate -m "drift-check" --rev-id drift_check
# fail if the generated file contains any op.create_table/drop_table/add_column/
# drop_column/alter_column, then delete it
```

This also closes the "autogenerate produces empty diff" chore in the roadmap's
Later section — note that in the PR description so the chore gets struck.

## Frontend Changes

**None.** No file under `frontend/` is touched by this ticket.

## Data Model / Migration Notes

- **No migration is written.** Tables, columns, indexes and constraints are
  byte-identical; only the Python module a class is declared in changes.
- **No upsert-key changes** — no `fetch_*` body is touched.
- Verify the four existing migrations in `backend/alembic/versions/` don't import
  from `app.models` in a way the package split breaks. The `__init__.py` re-export
  should cover it, but grep them and confirm rather than assume (AC-6).
- `backend/alembic/env.py` line 23 (`from app.models import Base`, feeding
  `target_metadata = Base.metadata`) is the single most important import to preserve.
  Confirmed present 2026-09-11.

## Sequencing

Full suite green after **each** step, not just at the end. One commit per step
keeps the bisect useful if something breaks.

1. **Create the three package skeletons** with `__init__.py` files. No moves yet.
2. **Move `shared/`** (4 modules: status router, `service_status`, `source_run`,
   `topic_matcher`). Smallest blast radius, and it unblocks the classification
   question. Update importers — note `nyt.py`, `reddit_trending.py` and
   `wikipedia_trending.py` all import `topic_matcher`.
3. **Move `monitor/`** (27 modules). Update `main.py` and `scheduler.py` imports.
4. **Move `elections/`** (16 modules). Same.
5. **Delete the now-empty `app/routers/` and `app/services/`.** Confirm nothing
   resolves at the old paths — clear `__pycache__` before believing the result.
6. **Split `models.py`** into the package. Run the autogenerate check locally here,
   before CI sees it.
7. **Add `test_module_boundaries.py`.** Verify it fails on a deliberate violation,
   then revert the violation.
8. **Add the CI drift step.**

## Documentation Updates

- [ ] `SOURCES.md` — no source changes, but the `Service` column paths
      (`votehub.py`, `house_polls.py`, …) are now package-relative. Update them, and
      fix the stale "The Python runtime is 3.9" line while in there.
- [ ] `.env.example` — no new env vars in this ticket.
- [ ] `CLAUDE.md` — add a line naming the three packages and pointing at the
      boundary test, so the next session doesn't have to rediscover the seam.
- [ ] `docs/ROADMAP.md` — T1 → shipped with PR link, per repo convention.

## Risks / Rollback

- **Rollback is `git revert`.** No migration, no data change, no config change —
  this is the cheapest possible ticket to back out.
- **Biggest risk: a hidden import that only fires at runtime.** Static analysis and
  the suite won't catch a deferred import inside a function body. Mitigation: grep
  for `import` inside function bodies across the moved modules before step 5, and
  hit `/health` plus one route per domain on a local run.
- **Second risk: two `Base` objects.** Would look fine until autogenerate proposes
  dropping tables. Step 6's local check catches it before CI.
- **`__pycache__` staleness** can make a deleted module look importable. Clear it
  before trusting step 5.
- **Merge conflicts.** ~50 files move. Land this alone; don't run a parallel backend
  branch alongside it.
- **`create_all` in `main.py`'s lifespan** still runs as the release-1 safety net.
  It reads the same metadata, so it's unaffected — but don't take the opportunity to
  remove it here. Separate chore.

## Test Plan Pointer

See `04-test-cases.md` for the cases this implementation must satisfy.
