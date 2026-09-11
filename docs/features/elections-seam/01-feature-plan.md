# Feature Plan: Draw the Backend Elections/Monitor Seam

**Slug:** `elections-seam` &nbsp; **Owner:** Samuel &nbsp; **Status:** Approved &nbsp; **Date:** 2026-09-11

## Problem / Goal

`backend/app/` holds two products in one flat package. `routers/` is 14 modules in
one directory, `services/` is 33, and `models.py` is 25 model classes in one file.
Nothing in the layout says which half is the election/polling product and which is
the situational-awareness monitor, and nothing stops a future change from coupling
them. Roadmap item #9 plans to extract the elections product into its own project;
every later ticket in that plan (second database, second deploy, repo split) is a
mechanical move if the seam exists first and a rewrite if it doesn't.

This ticket draws that boundary inside the current package and makes it enforced,
with no behaviour change and no schema change. It is T1 of item #9 and the
prerequisite for T2 (`scheduler-split`).

## Context

- Touches **every** domain structurally, but changes no data source, route URL,
  response shape, or table. Nothing in `SOURCES.md` gains or loses a row.
- Builds on the July feature plan at `docs/features/extract-elections-app/01-feature-plan.md`,
  which asserted the backend has no cross-domain imports.
- **That assertion was re-verified 2026-09-11 and holds.** An import scan across
  `routers/` and `services/` found exactly one candidate edge — `nyt.py`,
  `reddit_trending.py` and `wikipedia_trending.py` all import
  `services/topic_matcher.py`. On inspection `topic_matcher` is a generic
  word-overlap string matcher used for cross-source trend dedup, with no election
  concepts in it. It belongs to the monitor side (or to shared utilities), not to
  elections. With it classified correctly there are **zero elections↔monitor
  imports**.
- Why now: the extraction has a November deadline attached to the tickets that
  ship a public polling URL, and this is the first of them. It is also the
  cheapest one to get wrong silently, because a half-drawn seam looks finished.

## Scope

What's in for v1:

- [ ] New/changed data source (upstream, cadence) — **no**
- [x] New/changed backend service (`backend/app/services/`) — every module moves; none changes
- [x] New/changed API route (`backend/app/routers/`) — every module moves; **no URL changes**
- [ ] New/changed scheduler job (`backend/app/scheduler.py`) — imports update only; T2 does the split
- [x] New/changed data model (`backend/app/models.py`) — file splits into a package; **no Alembic migration**
- [ ] New/changed frontend component/page — **no**

Specifically:

- Regroup `routers/` and `services/` into three bounded groups: **elections**,
  **monitor**, **shared**.
- Split `models.py` into modules along the same boundary, keeping one `Base` and
  one Alembic metadata.
- Update every import site (`main.py`, `scheduler.py`, `backend/tests/`).
- Add a boundary test that **fails** if an elections module imports a monitor
  module or vice versa, so the seam is enforced rather than merely tidy.

## Non-Goals

- **Not splitting the scheduler.** That's T2 (`scheduler-split`); this ticket only
  fixes `scheduler.py`'s import paths.
- **Not splitting the database, the Alembic history, or the deploy.** T4 and T5b,
  deliberately deferred until after the election.
- **No frontend changes at all.** T3.
- **No route URL, response shape, table, or column changes.** If this ticket
  produces an Alembic autogenerate diff, something went wrong.
- **Not deciding the final home for `ServiceStatus` / `SourceRun` / Astronomy.**
  They go to `shared/` as a holding position; T6 decides permanently.
- Not renaming the product. Package names here are internal and don't commit to
  whatever the polling app ends up being called.

## Proposed Approach

**1. Target layout.** Internal package names, not product names:

```
backend/app/
  elections/   routers/ services/     polls, candidates, economist, votehub,
                                      forecasts, markets
  monitor/     routers/ services/     trends, news, weather, hazards, climate,
                                      astronomy
  shared/      routers/ services/     status (service status + source health),
                                      topic_matcher and other domain-free utilities
  models/      __init__.py, elections.py, monitor.py, shared.py
  database.py  auth.py  main.py  scheduler.py     (unchanged location)
```

**2. Model split, single `Base`.** `models/__init__.py` re-exports every class from
the three modules so `from app.models import HousePoll` keeps working unchanged.
All three modules import the same `Base` from `app.database`, so Alembic's
metadata is identical before and after. The classes divide 11 elections
(`Candidate`, `CandidateIssueTag`, `HousePoll`, `CompetitiveDistrict`,
`HouseRetirement`, `EconYouGovReport`, `EconYouGovCrosstab`, `VoteHubPoll`,
`PredictionMarket`, `MarketSnapshot`, `GenericBallotAggregate`), 12 monitor
(`TrendCluster`, `Trend`, `Article`, `Summary`, `TrendSnapshot`, `WikiPage`,
`WikiPageView`, `NewsArticle`, `RegionalWeather`, `Earthquake`, `NWSAlert`,
`ClimateEvent`), 2 shared (`ServiceStatus`, `SourceRun`).

**3. Proof of no schema change.** `alembic revision --autogenerate` must produce an
empty diff after the move. This is the acceptance bar for the model split and
should be asserted in CI, which also delivers the "autogenerate produces empty
diff" chore already sitting in the roadmap's Later section.

**4. Enforce the boundary.** A test walks the import graph of `app/elections/**`
and `app/monitor/**` and fails on any edge between them. Without this, the seam
decays the first time someone is in a hurry, and T4 through T7 get harder again.

**5. Sequencing within the ticket.** Move `shared/` first (smallest, unblocks the
classification question), then `monitor/`, then `elections/`, then the model
package, then the boundary test. Full suite green after each step, not just at the
end.

## Open Questions / Risks

- **Package naming.** `elections/` and `monitor/` are the working proposal. They
  avoid committing to the product name (still undecided, and blocking T3 rather
  than this ticket). Alternatives: `polling/`, `situation/`. Worth settling before
  Code starts, since it's in every path.
- **Keep `app.models` as a shim, or update all call sites?** Recommendation: keep
  the shim via `models/__init__.py`. It makes this diff dramatically smaller and
  costs nothing; T7 can decide whether to drop it.
- **Where does `topic_matcher` live?** It's domain-free by inspection but used only
  by monitor services today. `shared/services/` is the honest placement; `monitor/`
  is the simpler one. Low stakes either way — flagging because it was the one
  module the automated classification got wrong.
- **Alembic migration files reference model import paths.** Need to confirm the
  four existing migrations in `backend/alembic/versions/` don't import from
  `app.models` in a way the split breaks. The `models/__init__.py` shim should
  cover this, but it must be checked, not assumed.
- **Diff size.** This touches ~50 files. It is mechanical, but it is not small, and
  it will conflict with any other in-flight backend branch. Land it alone.
- **Failure isolation is not at risk** — no scheduler or error-handling logic
  changes in this ticket.
- **Dependency:** T2 (`scheduler-split`) should start only after this merges.

## References

- `docs/features/extract-elections-app/01-feature-plan.md` — the parent plan (item #9)
- `docs/ROADMAP.md` — Extraction tickets section, T1
- `SOURCES.md` — domain boundaries the grouping follows
- `docs/features/status-admin-consolidation/` — prior art for a no-behaviour-change refactor through this pipeline
