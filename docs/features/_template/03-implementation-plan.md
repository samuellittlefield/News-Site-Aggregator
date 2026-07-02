<!--
TEMPLATE: Implementation Plan
File location once approved: news-site/docs/features/<slug>/03-implementation-plan.md
This is the handoff doc to Claude Code — be concrete about files touched and sequencing.
-->

# Implementation Plan: <Feature Name>

**Slug:** `<slug>` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
One or two sentences on the technical approach, for someone opening this cold in Claude Code.

## Backend Changes
*(Python 3.9 — use `Optional[...]`, not `X | Y`)*

| File | Change |
|---|---|
| `backend/app/services/<new_or_existing>.py` | e.g. new `async def fetch_x(db)` |
| `backend/app/models.py` | new/changed model + fields |
| `backend/alembic/versions/` | migration for the above |
| `backend/app/routers/<name>.py` | new/changed route |
| `backend/app/scheduler.py` | new job registration + cadence |

Note the upstream API (auth, rate limits, response shape) and how failures are isolated so one bad source doesn't starve the rest.

## Frontend Changes
| File | Change |
|---|---|
| `frontend/src/api/client.ts` | new API call |
| `frontend/src/components/<Name>.tsx` | new/changed component |
| `frontend/src/pages/<Name>Page.tsx` | new/changed page, if applicable |

## Data Model / Migration Notes
Any schema changes, backfill needs, or upsert-key considerations.

## Sequencing
Order of work — what has to land before what (e.g. migration → service → router → scheduler → frontend).

1. ...
2. ...
3. ...

## Documentation Updates
- [ ] `SOURCES.md` updated if this adds/changes a data source
- [ ] `.env.example` updated if new env vars/secrets are needed

## Risks / Rollback
What could go wrong, and how to back it out (feature flag, revert migration, disable scheduler job).

## Test Plan Pointer
See `04-test-cases.md` for the cases this implementation must satisfy.
