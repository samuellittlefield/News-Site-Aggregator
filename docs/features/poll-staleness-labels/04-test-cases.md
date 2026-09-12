# Test Cases: Staleness Labelling on Poll Averages

**Slug:** `poll-staleness-labels` &nbsp; **Source:** `02-acceptance-criteria.md`

## Coverage Map

| AC | Test IDs |
|---|---|
| AC-1 Provenance fields | TC-1 |
| AC-2 Existing fields identical | **TC-2** |
| AC-3 Forecast unaffected | **TC-3** |
| AC-4 Date visible | TC-8 |
| AC-5 Stale marker | TC-4, TC-9 |
| AC-6 Thin average | TC-5, TC-10 |
| AC-7 Empty state | TC-6, TC-11 |
| AC-8 Empty table | TC-7 |
| AC-9 Both poll types | TC-12 |
| AC-10 Drain documented | TC-13 |

## Backend

### TC-1 — Provenance fields present and correct (covers AC-1)
- **Type:** unit. Seed polls with known end dates; assert `newest_fieldwork_end` and `oldest_fieldwork_end` equal the max/min actually averaged, not the max/min in the table.

### TC-2 — Existing keys byte-identical (covers AC-2)
- **Type:** integration. Diff `/api/votehub/approval` and `/api/votehub/generic-ballot` against the pre-change fixtures, ignoring the two new keys.
- **Expected:** every other key identical in name, type and value. Any drift fails the ticket.

### TC-3 — Forecast output unchanged (covers AC-3)
- **Type:** integration. Diff `/api/forecasts/congress` against its pre-change fixture.
- **Expected:** `swing_d`, `swing_source`, `dem_prob`, `rep_prob`, `median_dem_seats` identical for both chambers. **The hard gate — if this fails, stop and report rather than adjusting the fixture.**

### TC-4 — Stale threshold boundary (covers AC-5)
- **Type:** unit. Newest fieldwork at 9, 10 and 11 days old.
- **Expected:** the classifier's stale/fresh verdict flips exactly once, at the documented boundary.

### TC-5 — Thin-average classification (covers AC-6)
- **Type:** unit. `n_polls` of 1, 2 and 3.
- **Expected:** 1 and 2 classify as thin, 3 does not.

### TC-6 — `None` on empty window (covers AC-7)
- **Type:** unit. Polls exist, all older than the window.
- **Expected:** `compute_average` returns `None` — unchanged behaviour — and the route returns `average: null` without error.

### TC-7 — Genuinely empty table (covers AC-8)
- **Type:** unit. No rows for that poll type.
- **Expected:** returns `None`, no exception, no fabricated date.

### TC-12 — Both poll types behave identically (covers AC-9)
- **Type:** unit. Run TC-4/5/6 against `generic-ballot` as well as `approval`.

### TC-13 — Drain exposure documented (covers AC-10)
- **Type:** unit. Assert `SOURCES.md` or the `forecast_model` docstring mentions the drain-to-tier-2 path.

## Frontend

All manual — no Vitest configured. `npm run dev`, Polls page.

### TC-8 — Date is visible at rest (covers AC-4)
- Load the Polls page. Newest fieldwork date readable on the approval card, `ApprovalSection` and the generic ballot bar without hover or click.

### TC-9 — Stale state renders (covers AC-5)
- With today's real data (approval newest 2026-08-28, ~15 days), the approval card shows the stale marker and the generic ballot bar does not.
- Marker distinguishable by more than color alone.

### TC-10 — Thin state renders (covers AC-6)
- Point at a fixture with 1 poll. Count is prominent, not fine print.
- **Also worth a look on 2026-09-16 against live data**, when this becomes the real state.

### TC-11 — Empty state renders (covers AC-7)
- Force `average: null`. Card shows explicit no-recent-polling copy naming the last known date. **It must not vanish** — the pre-change behaviour.
- Also check `ApprovalSection`'s Economist net and the sparkline degrade sensibly rather than disappearing with it.

## Edge Cases & Failure Modes

- **Indefinite upstream silence is the expected condition**, not an exception.
- No ingestion change, so no upsert or isolation cases.
- **Timezone:** verify a poll ending 2026-08-28 UTC displays as 28 August, not the 27th, in US locales.
- No new upstream, so no rate-limit or auth cases.

## Regression Check

- `GET /api/forecasts/congress` — both chambers, `swing_source` still `votehub`
- `GET /api/polls/generic-ballot` — unchanged shape and values
- Polls page — district map, poll carousel, recent polls list all still render
- Dashboard `PollsPanel` and `MarketsPanel` — they consume the same endpoints
- Admin Data Sources panel — `votehub_job` still success

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
