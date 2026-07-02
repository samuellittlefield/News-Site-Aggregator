# Implementation Plan: Hacker News Trending Source

**Slug:** `hacker-news-trending` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Add a new ingestion service that mirrors `reddit_trending.py`'s shape — fetch, filter, de-dupe, upsert into `Trend` — sourced from HN's public Firebase API, and wire it into the existing enrichment scheduler job. No new table, route, or frontend component.

## Backend Changes
*(Python 3.9 — use `Optional[...]`, not `X | Y`)*

| File | Change |
|---|---|
| `backend/app/services/hackernews_trending.py` | New. `async def fetch_hn_trending(db) -> list`: GET `/v0/topstories.json`, take top ~50 IDs, GET each `/v0/item/{id}.json` (batched/concurrent via `httpx.AsyncClient`), filter `score >= MIN_SCORE` and not dead/deleted, de-dupe via `topic_matcher.find_match` against active trends (same as Reddit), upsert into `Trend` with `source="hackernews"`. |
| `backend/app/models.py` | No change — reuse `Trend`, `source` column already supports arbitrary string values. |
| `backend/alembic/versions/` | No migration needed. |
| `backend/app/routers/*` | No change — HN trends surface through existing `/api/trends*` routes automatically. |
| `backend/app/scheduler.py` | Add `from app.services import hackernews_trending as hn_trending_service` and call `await hn_trending_service.fetch_hn_trending(db)` alongside the existing Reddit call (same enrichment step, ~line 87 per current `reddit_trending_service` call), log count same as Reddit. |

Failure isolation: wrap the HN fetch in the same try/except-and-log pattern as `reddit_trending.py` so a dead HN API doesn't block Wikipedia/NYT/Reddit enrichment in the same job.

## Frontend Changes
None. `TrendCarousel` / `TrendCard` already render any `Trend` row regardless of `source`.

## Data Model / Migration Notes
None — no schema changes. Confirm `source` column has no enum/check constraint that would reject `"hackernews"` (grep `models.py` — it's a plain `String`, so no constraint to update).

## Sequencing
1. Write `hackernews_trending.py` with fetch + filter + upsert logic, unit-testable in isolation.
2. Wire into `scheduler.py` enrichment step.
3. Run locally, verify rows land in `trends` with `source="hackernews"` and surface in the Trends tab.
4. Tune `MIN_SCORE` threshold based on a day of real data (per feature plan's open question).
5. Update `SOURCES.md` with the new row under **Trends & Attention**.

## Documentation Updates
- [x] `SOURCES.md` — add a row: HN topstories → `hackernews_trending.py` → hourly → via trends pipeline → Trends tab.
- [ ] `.env.example` — not needed, HN API requires no auth/key.

## Risks / Rollback
Lowest-risk feature in the pipeline: no migration, no route, no frontend change. Rollback is just removing the scheduler call and (optionally) the service file — no data cleanup needed since HN-sourced trends are indistinguishable in structure from any other trend row and won't break anything if left in place.

## Test Plan Pointer
See `04-test-cases.md`.
