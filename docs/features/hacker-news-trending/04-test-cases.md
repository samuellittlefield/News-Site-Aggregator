# Test Cases: Hacker News Trending Source

**Slug:** `hacker-news-trending` &nbsp; **Source:** `02-acceptance-criteria.md`

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2 |
| AC-3 | TC-3 |
| AC-4 | TC-4 |

## Backend

### TC-1 — High-score HN story becomes a Trend row (covers AC-1)
- **Type:** integration (service function)
- **Setup:** mock `httpx` responses for `/v0/topstories.json` and `/v0/item/{id}.json` with one story at score 500 (above threshold), title present, not dead.
- **Steps:**
  1. Call `fetch_hn_trending(db)` directly against a test DB session.
  2. Query `Trend` table for `source="hackernews"`.
- **Expected Result:** exactly one new `Trend` row exists with the mocked title and `source="hackernews"`.
- **Automation note:** target `backend/tests/test_hackernews_trending.py` with pytest once a harness exists; until then, run via a scratch script or Python REPL with a mocked `httpx.AsyncClient`.

### TC-2 — Low-score story is filtered (covers AC-2)
- **Type:** integration (service function)
- **Setup:** mock response with one story at score 10 (below `MIN_SCORE`).
- **Steps:** call `fetch_hn_trending(db)`, query `Trend` for that title.
- **Expected Result:** no row created.

### TC-3 — Matching title boosts existing trend instead of duplicating (covers AC-3)
- **Type:** integration (service function)
- **Setup:** seed an active `Trend` with a title closely matching the mocked HN story's title.
- **Steps:** call `fetch_hn_trending(db)`, inspect the existing trend's `signal_score` and `sources_list`, and confirm row count for that title.
- **Expected Result:** `signal_score` increased, `"hackernews"` present in `sources_list`, still exactly one row for that title (no duplicate).

### TC-4 — Live API smoke test (manual, no mocks)
- **Type:** manual, against the real HN API
- **Steps:**
  1. Run the backend locally (`uvicorn` per repo README/Procfile).
  2. Trigger the enrichment job (manually invoke or wait for scheduler tick).
  3. Check logs for the "HN trending: N new trends added" line (mirroring the existing Reddit log message).
  4. Query `/api/trends` (or check the Trends tab in the frontend) for entries with plausible HN story titles.
- **Expected Result:** at least one real HN story appears within a reasonable time, with no errors logged.

## Frontend

No frontend-specific test cases — HN trends render through the existing `TrendCarousel`/`TrendCard` path, already covered by that path's existing behavior (per AC-4, no new UI surface).

## Edge Cases & Failure Modes
- HN API down/timeout → job logs and returns `[]`, other enrichment steps (Wikipedia, NYT, Reddit) still run in the same scheduler tick.
- Item marked `"dead": true` or missing `"title"` → skipped without error.
- Empty `trends` table (first run) → insert succeeds without error.

## Regression Check
- Confirm existing Reddit/Wikipedia/NYT trend ingestion in the same scheduler job still runs and logs correctly after adding the HN call (i.e. one bad addition doesn't break the others — this is the whole point of the isolation pattern).
- Confirm `/api/trends*` endpoints' existing response shape/tests (manual, since none automated yet) are unaffected.

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main *(dry run — not a real merge)*
