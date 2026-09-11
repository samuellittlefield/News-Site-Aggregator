# Feature Plan: Split the Scheduler into Two Job Groups

**Slug:** `scheduler-split` &nbsp; **Owner:** Samuel &nbsp; **Status:** Approved &nbsp; **Date:** 2026-09-11

## Problem / Goal

All 17 ingestion jobs run in one APScheduler instance with no notion of which
product they serve, so there is no way to run, pause, or deploy the election
ingestion independently of the news/weather ingestion. T5b eventually needs
exactly that, and it is far safer to establish the grouping now, inside one
process, than to discover the coupling while standing up a second deploy.

There is a second, worse problem underneath it. **The set of jobs is enumerated in
four separate hand-maintained places, and they already disagree.**

| Enumeration | Location | Count |
|---|---|---|
| `SOURCE_CADENCE` | `services/source_run.py` | 17 |
| `start_scheduler()` | `scheduler.py` | 17 |
| `_startup_refresh()` | `main.py` | 15 |
| `_do_full_refresh()` | `main.py` | 12 |

`_do_full_refresh` is what the public **Refresh** button on `TrendsPage` calls via
`POST /api/refresh`. It omits `refresh_candidates`, `refresh_economist`,
`refresh_house_polls`, `refresh_retirements` and `run_issue_tagger` — **every
election-side job**. Clicking Refresh today does not refresh any polling data, and
nothing surfaces that. `_startup_refresh` separately omits `refresh_climate` and
`run_issue_tagger`.

Splitting the scheduler while four lists disagree would just produce eight lists
that disagree. So this ticket collapses them to one registry first, then splits on
that.

## Context

- Touches the scheduler and startup path, which serve **all** domains. No upstream
  data source, route URL, response shape, or table changes.
- Builds directly on `ingestion-health` (PR #9), which established `SOURCE_CADENCE`
  in `services/source_run.py` as the single source of truth for job id → label →
  expected cadence, shared by the scheduler and `GET /api/status/sources`. Its
  TC-7 already diffs registered job ids against `SOURCE_CADENCE` to catch drift —
  this ticket extends that idea to the other two lists, which TC-7 never covered.
- Depends on **T1 (`elections-seam`)** having merged, so each job's domain is a
  property of where its service already lives rather than a new hand-maintained
  label.
- Why now: T2 of roadmap item #9, targeted before the election because it never
  touches the database.

## Scope

- [ ] New/changed data source — **no**
- [x] New/changed backend service — `services/source_run.py` gains a domain field; no fetch logic changes
- [x] New/changed API route — `POST /api/refresh` behaviour changes (see Open Questions)
- [x] New/changed scheduler job — all 17 regrouped; **no cadence changes, no jobs added or removed**
- [ ] New/changed data model — **no, and no Alembic migration**
- [ ] New/changed frontend component/page — **no** (unless `/api/refresh` becomes domain-scoped)

Specifically:

- Extend `SOURCE_CADENCE` into a single job registry: id → function, cadence,
  label, **domain** (`elections` | `monitor` | `shared`).
- Derive `start_scheduler()`, `_startup_refresh()` and `_do_full_refresh()` from
  that one registry. Delete the three hand-maintained lists.
- Gate registration by group so either domain's jobs can be disabled without code
  changes.
- Close the `/api/refresh` gap the consolidation exposes.
- Extend the drift test to cover all enumerations, not just registration.

## Non-Goals

- **Not two processes or two deploys.** T5b, after the election. This is one
  APScheduler instance with grouped, gateable jobs.
- **No cadence changes.** Every job keeps the interval it has today. If a cadence
  looks wrong, that's a separate ticket.
- **Not adding `refresh_breakout` to the scheduler.** It's deliberately unscheduled
  (on-demand only) and stays that way; the registry should record that explicitly
  rather than leaving it as an unexplained omission.
- **Not fixing any individual source.** The Economist scraper is roadmap item #10.
- Not changing `DISABLE_SCHEDULER=1` semantics, which the test suite depends on.

## Proposed Approach

**1. One registry.** Grow the existing `SOURCE_CADENCE` entry into a record
carrying the refresh callable and a domain alongside the label and cadence it
already holds. It stays in `shared/services/source_run.py` so both the scheduler
and the status route keep importing from one place. Jobs that should not run on a
manual refresh (`run_issue_tagger`, weekly and expensive) or are unscheduled
(`refresh_breakout`) carry explicit flags rather than being silently absent.

**2. Everything derives from it.** `start_scheduler(groups=...)` iterates the
registry and registers the jobs whose domain is enabled. `_startup_refresh()` and
`_do_full_refresh()` iterate the same registry with their respective flags. The
three hand-written lists disappear, which is what makes the drift structurally
impossible rather than merely fixed once.

**3. Group gating.** An env var — working name `SCHEDULER_GROUPS`, default
`elections,monitor` (both, i.e. today's behaviour) — selects which groups
register. `DISABLE_SCHEDULER=1` keeps its current meaning of "none, and no startup
refresh," and keeps precedence. Needs a line in `.env.example`.

**4. Preserve what already works.** Per-job try/except failure isolation, the
`SourceRun` success/failure recording inside each `refresh_*`, and the startup
timeout budgets in `_safe_refresh` all stay exactly as they are. This ticket
changes *which* jobs run and *where the list comes from*, never how a job behaves
when its upstream misbehaves.

**5. Test the drift shut.** Extend `ingestion-health`'s TC-7 so registered ids,
startup-refresh ids and manual-refresh ids are each checked against the registry.
That test failing is the whole point: it's what stops list five from appearing.

## Open Questions / Risks

- **`POST /api/refresh` scope — DECIDED 2026-09-11 (option 3).** The public button
  keeps running only the cheap monitor jobs and says so in the UI; the election
  jobs get a separate refresh path gated by `require_admin_key` (already built in
  PR #10, so the cost is small).
  Rejected: "refresh everything." `/api/refresh` is public and unauthenticated, and
  the excluded jobs are in a different weight class — FEC is ~50-60 paginated API
  calls per run (`/candidates/` + `/candidates/totals/` for House and Senate, plus
  election dates), house polls is ~50-60 Wikipedia calls (one per state plus one per
  district section), and the issue tagger is up to 50 Groq LLM calls. With a 60s
  cooldown the endpoint permits 60 triggers an hour, so refreshing everything would
  allow ~3,600 FEC calls/hour against a 1,000/hour key limit — reachable by one
  person clicking a public button. The cooldown also gates *triggering*, not
  *concurrency*: a full elections refresh takes minutes, so runs would overlap and
  paginations would compete, which is the exact failure `fec_candidates.py` already
  warns about in comments ("silently dropped multi-million-dollar frontrunners onto
  lost pages"). This also lands better for T3, which wants its own refresh control
  rather than a shared button that does half the work.
- **Was the original omission deliberate?** Read: the FEC exclusion looks
  deliberate, or at least correct by accident — it's the one job with a 600s startup
  budget and obvious cost. The other four look like drift; `refresh_retirements` is a
  single Wikipedia call and has no reason to be excluded. Either way the destination
  is the same, so this isn't blocking.
- **Cooldown on the new admin-gated elections refresh.** The public button keeps its
  existing 60s cooldown unchanged. The new gated path needs its own answer — a longer
  cooldown, or an in-flight guard that rejects a trigger while a run is still going.
  An in-flight guard is the more correct fix, since the problem is overlap rather than
  frequency.
- **Circular import risk.** The registry holds references to `refresh_*` functions
  that live in `scheduler.py`, while `scheduler.py` imports the registry from
  `source_run.py`. Needs a deliberate structure — a registration call at import
  time, or the registry holding dotted paths — rather than being discovered
  mid-implementation.
- **Dependency:** blocked on T1 merging first.

## References

- `docs/features/ingestion-health/` — `SOURCE_CADENCE`, `SourceRun`, TC-7 drift test
- `docs/features/write-endpoint-auth/` — the `/api/refresh` cooldown decision
- `docs/features/elections-seam/01-feature-plan.md` — T1, prerequisite
- `docs/ROADMAP.md` — Extraction tickets section, T2
