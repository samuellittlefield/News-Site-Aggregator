# Test Cases: Fix In-House Forecast Model's Silent Swing Fallback

**Slug:** `forecast-model-swing-fallback-fix` &nbsp; **Source:** `02-acceptance-criteria.md`

> Backend cases are automated pytest using `backend/tests/`'s existing `client`/`db` fixtures. The autouse `respx_router` guard (from `conftest.py`) doubles as a check that no test in this file accidentally triggers a live Wikipedia call — any unmocked outbound request raises automatically.

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2 |
| AC-3 | TC-3 |
| AC-4 | TC-1, TC-2, TC-3 (assert `swing_source` in each) |
| AC-5 | TC-6 |
| AC-6 | TC-4 |
| AC-7 | TC-5 |
| (edge cases) | TC-7, TC-8, TC-9, TC-10 |

## Backend

### TC-1 — VoteHub tier wins when healthy (covers AC-1, AC-4)
- **Type:** integration, `backend/tests/test_forecast_swing_source.py`
- **Setup:** seed `VoteHubPoll` rows with `poll_type="generic-ballot"`, recent `end_date`, parseable `dem`/`rep`; leave `GenericBallotAggregate` empty
- **Steps:** `client.get("/api/forecasts/congress")`
- **Expected Result:** `house.model.swing_source == "votehub"`; `swing_d` reflects the seeded VoteHub margin minus the 2024 baseline (not 0)

### TC-2 — Aggregator tier fires when VoteHub is empty (covers AC-2, AC-4)
- **Type:** integration
- **Setup:** empty `VoteHubPoll` table (or none within window); seed `GenericBallotAggregate` with a few rows (mix of dem/rep values)
- **Steps:** `client.get("/api/forecasts/congress")`
- **Expected Result:** `swing_source == "aggregator"`; `swing_d` reflects the mean of the seeded aggregator rows, not 0

### TC-3 — Static baseline only when both tiers are empty (covers AC-3, AC-4)
- **Type:** integration
- **Setup:** both `VoteHubPoll` and `GenericBallotAggregate` empty
- **Steps:** `client.get("/api/forecasts/congress")`
- **Expected Result:** `swing_source == "fallback"`, `swing_d == 0` — this is the one case where 0 is now a *labeled* fallback, not an ambiguous silent one

### TC-4 — Market-consensus fields unaffected (covers AC-6)
- **Type:** integration, regression
- **Setup:** seed `PredictionMarket` rows (Kalshi) as in existing forecast tests; combine with each of TC-1/TC-2/TC-3's polling setups in turn
- **Steps:** `client.get("/api/forecasts/congress")`
- **Expected Result:** top-level `dem_prob`/`rep_prob`/`sources` for each chamber are identical across all three polling scenarios — market consensus doesn't move regardless of which environment tier the model used

### TC-5 — `/api/forecasts/model` reflects the same tier logic (covers AC-7)
- **Type:** integration
- **Setup:** same three scenarios as TC-1/2/3
- **Steps:** `client.get("/api/forecasts/model")` for each
- **Expected Result:** `swing_source` on the returned house/senate blocks matches the same tier as the corresponding `/congress` call — no divergent logic path between the two endpoints

### TC-7 — Partial VoteHub data treated as no signal (covers Data Quality edge case)
- **Type:** integration
- **Setup:** seed `VoteHubPoll` rows with `poll_type="generic-ballot"`, recent `end_date`, but `dem`/`rep` both `None` (unparsed); seed `GenericBallotAggregate` with valid rows
- **Steps:** `client.get("/api/forecasts/congress")`
- **Expected Result:** `swing_source == "aggregator"` — a present-but-unparseable VoteHub poll must not count as "VoteHub tier succeeded" nor as "VoteHub tier definitively failed forever," it just falls through to tier 2 for this request

### TC-8 — `refresh_house_polls` persists aggregator rows, upserts don't duplicate (covers implementation persistence)
- **Type:** unit, `backend/tests/test_house_polls.py` (extend) or new file
- **Setup:** mock the Wikipedia fetch (`respx_router`) to return a fixed set of aggregator rows
- **Steps:** call `refresh_house_polls(db)` twice in a row
- **Expected Result:** `GenericBallotAggregate` has exactly one row per distinct `source` after both runs (upsert, not append) — mirrors the idempotency pattern in `test_kalshi_upsert.py`

### TC-9 — Persistence failure doesn't break district-poll refresh (covers isolation)
- **Type:** unit
- **Setup:** monkeypatch the `GenericBallotAggregate` upsert to raise
- **Steps:** call `refresh_house_polls(db)`
- **Expected Result:** the function still completes and district polls are still refreshed/returned — the new persistence step is wrapped so it can't take down the rest of the function, consistent with this codebase's isolation convention

### TC-10 — `/api/polls/generic-ballot` response is unchanged (covers AC edge case / regression)
- **Type:** integration, regression
- **Setup:** seed the same data as an existing generic-ballot test (or TC-1/TC-2's setup)
- **Steps:** `client.get("/api/polls/generic-ballot")` before and after this feature's changes (or just assert current expected shape/values post-change)
- **Expected Result:** identical response shape and values to pre-fix behavior — this fix adds a new read path for the model, it does not touch this route's own live-fetch + VoteHub-average logic

## Frontend

### TC-6 — Model card shows a fallback indicator only when `swing_source === "fallback"` (covers AC-5)
- **Type:** manual/click-through
- **Steps:**
  1. With backend seeded so `swing_source == "fallback"` (e.g. clear test data locally), load the forecast/model card in the browser
  2. Repeat with backend seeded so `swing_source == "votehub"` or `"aggregator"`
- **Expected Result:** fallback case shows a visible "not based on current polling" indicator; the other two cases render as today, no indicator
- **Automation note:** target a Vitest component test once that harness exists (currently unshipped roadmap chore)

## Edge Cases & Failure Modes
- Partial/unparseable VoteHub data → falls through cleanly to tier 2, not treated as a hard failure (TC-7)
- Both tiers empty → static baseline still fires, but now labeled (TC-3)
- Aggregator persistence failing shouldn't break the broader `refresh_house_polls` job (TC-9)
- No live network call introduced into `/api/forecasts/congress`'s request path — implicitly covered by every integration test in this file running under the autouse `respx_router` guard, which raises on any unmocked outbound HTTP call

## Regression Check
- `/api/polls/generic-ballot` — unchanged (TC-10)
- Existing `test_house_polls.py` district-poll tests — should still pass unmodified after adding the aggregator-persistence step to `refresh_house_polls`
- Existing forecast/market-consensus tests (if any) — should still pass; TC-4 explicitly re-confirms market fields are stable across all three environment-tier scenarios

## Sign-off
- [ ] All test cases pass (`pytest backend/tests/` for TC-1–TC-5, TC-7–TC-10; manual click-through for TC-6)
- [ ] Samuel has reviewed results before merge to main
