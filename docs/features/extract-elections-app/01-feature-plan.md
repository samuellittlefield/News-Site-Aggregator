# Feature Plan: Extract Elections/Polling into a Standalone Project

**Slug:** `extract-elections-app` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-23

## Problem / Goal

News-site has grown into two products sharing one repo, one Postgres database, one
FastAPI process, and one frontend build: a general situational-awareness
aggregator (trends, news, weather, hazards) and an election forecasting/polling
product (candidates, House/Senate polls, prediction markets, forecasts). They
don't share a narrative, and the codebase reflects that — the Dashboard is just
a grid of unrelated panels, not a synthesized view. Recent brainstorming (command
palette / cross-domain search) kept running into this seam rather than past it.
The goal is to separate the election/polling product into its own project so
each can develop its own identity, without a risky one-shot cutover.

## Context

- Touches **Politics & Polling** and **Forecasting** (per `SOURCES.md`) as the
  extraction target; **News**, **Trends & Attention**, and **Weather, Hazards &
  Nature** stay behind as `news-site`.
- **Service Status** (`SourceRun`, `ServiceStatus`, the Admin page's health
  panels) and **Astronomy** are cross-cutting/orphaned and don't belong to
  either side cleanly — see Open Questions.
- Prompted by 2026-07-23 brainstorming: a command-palette/search feature kept
  feeling "disjointed," which turned out to be a symptom of the two-product
  architecture rather than a search-UX problem. Samuel decided the right move
  is a real split, done gradually since there's no urgency.

## What the codebase actually looks like today (grounding for the plan)

- **Backend has no cross-domain imports already.** `backend/app/routers/` and
  `backend/app/services/` for candidates/polls/markets/forecasts never import
  from the trends/news/weather/hazards modules, and vice versa. The domains are
  logically separable; they're just deployed as one process.
- **One scheduler, 17 jobs, one process** (`backend/app/scheduler.py`) —
  ingestion for both domains runs in the same APScheduler instance.
- **One Postgres DB** (`newsdb`), **one Alembic history** (4 migrations, one a
  squashed baseline), **one Railway deploy** (single `Procfile`), **one admin
  key** (`ADMIN_API_KEY`).
- **Frontend is one Vite/React app, one `package.json`.** Election-side deps
  (`deck.gl`, `leaflet`, `react-leaflet` — for the district map) sit alongside
  the rest with no build-level separation. `App.tsx` has a single nav bar/header
  shared by both domains. `client.ts` (987–1050 lines, already flagged in
  roadmap item #5) mixes API calls for both domains with no module boundary.
- **`AdminPage`** shows `SourceHealthSection` + `ServiceStatusSection` for *all*
  17 jobs across both domains in one view — genuinely shared infra, not
  incidentally shared.
- **No test harness split either** — CI (`ci.yml`) runs one pytest job against
  one `newsdb_test` and one frontend build job.

## Scope

What's in for the overall effort (broken into sequenced tickets in the
implementation plan, once this plan is approved):

- [ ] Draw the internal seam first: reorganize backend routers/services/models
      into two clearly-bounded groups (no physical split yet)
- [ ] Split the scheduler into two independently-disableable job groups
- [ ] Decouple `client.ts` and frontend routing into two domains (this can
      absorb roadmap item #5's TanStack Query migration rather than duplicate
      the effort)
- [ ] Stand up a second Postgres database + fresh Alembic history for the
      extracted elections app; migrate schema + data
- [ ] Stand up a second deploy target (Railway service or otherwise) for the
      extracted backend, and a second frontend build/deploy
- [ ] Decide and implement the home for cross-cutting pieces: `SourceRun`/
      `ServiceStatus` health tracking, Astronomy, and whatever Dashboard becomes
      on each side
- [ ] Physical repo split (new git repo, or two deployable apps in one repo —
      see Open Questions) and CI/CLAUDE.md/SOURCES.md updates on both sides

## Non-Goals

- No UI/UX redesign of either product as part of this — extraction only, not a
  rebrand. (Separate narrative/identity work can follow once each project
  exists on its own.)
- Not resolving roadmap item #5 (TanStack Query) as a standalone effort — it
  gets folded into the frontend-split ticket instead of done twice.
- Not deciding hosting/infra strategy beyond "two deploy targets exist" —
  cost, domain names, etc. are a separate decision if needed.
- No data migration of *historical* rows beyond what's needed for the new app
  to function (i.e., this isn't a data-warehouse/archival project).

## Proposed Approach

Gradual extraction, in roughly this order (each becomes its own ticket in the
implementation plan):

1. **Draw the seam, no physical split.** Reorganize backend code into two
   clearly-bounded packages/directories so the future split is a move, not a
   rewrite. Confirmed above: no cross-imports exist today, so this is
   mechanical, not risky.
2. **Split the scheduler** into two job groups that can be disabled/deployed
   independently (still one process for now).
3. **Split the frontend data layer** (`client.ts` → two modules) and nav
   (two distinct shells or a top-level product switcher), combined with the
   already-planned TanStack Query migration.
4. **Stand up the second database + Alembic history**, migrate the
   elections-side tables and data.
5. **Stand up the second deploy** (backend + frontend) for the elections app,
   running alongside `news-site` rather than replacing it.
6. **Resolve the cross-cutting pieces** (health tracking, Astronomy, Dashboard)
   — each needs an explicit decision, not a default.
7. **Physical repo split** (if going that route) and doc updates on both sides:
   new `CLAUDE.md`, `SOURCES.md` split or duplicated, CI split, this pipeline
   skill updated to know about two projects.

This ordering keeps `news-site` deployable and green at every step — nothing
requires a big-bang cutover, matching the "no urgency, do it gracefully" call.

## Open Questions / Risks

- **Two git repos, or one repo with two deployable apps?** Gradual extraction
  doesn't require splitting the repo immediately — could stay one repo/two
  services for a while and split the repo last, once the seam is proven. This
  materially changes ticket count and order.
- **Where does Astronomy live?** Belongs to neither domain cleanly.
- **What does the Dashboard become?** Right now it's the only page trying to
  represent "everything." Does `news-site` keep a scaled-down dashboard
  (trends/news/weather/hazards only)? Does the elections app get its own?
- **Health tracking (`SourceRun`/`ServiceStatus`/Admin page)** — duplicate the
  pattern in both apps, or keep one shared status surface? If duplicated, that's
  a real (small) rebuild, not a copy-paste.
- **Naming** — "elections app" is a placeholder in this doc; needs a real name
  before repo/deploy artifacts get created.
- **Cowork folder access** — this pipeline skill assumes one attached repo.
  Once a second project exists, planning for it needs its own folder mounted
  (or GitHub access) — worth confirming before we're mid-ticket on it.
- No upstream API risk here (this is entirely internal restructuring), so the
  usual "upstream stability" risk category doesn't apply.

## References

- `SOURCES.md` — domain boundaries (Politics & Polling / Forecasting vs. News /
  Trends & Attention / Weather, Hazards & Nature)
- `docs/ROADMAP.md` item #5 (`frontend-data-layer`) — folded into ticket 3 above
- 2026-07-23 Cowork conversation — command-palette brainstorm that surfaced the
  underlying architecture problem
