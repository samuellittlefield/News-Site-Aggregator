# Acceptance Criteria: Fix In-House Forecast Model's Silent Swing Fallback

**Slug:** `forecast-model-swing-fallback-fix` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: VoteHub live average still wins when available (no regression)
- **Given** VoteHub has one or more `generic-ballot` polls within the recency window with parseable `dem`/`rep` values
- **When** the model computes its environment
- **Then** it uses that VoteHub average exactly as it does today — this fix must not change behavior for the common case where VoteHub data is healthy

### AC-2: Aggregator average is used when VoteHub alone is empty
- **Given** VoteHub's `generic-ballot` query returns no usable average (empty window, or no polls with parseable party values)
- **And** the Wikipedia-sourced aggregator data (the same data behind the Polls page's 6-aggregator average) has usable rows
- **When** the model computes its environment
- **Then** it uses the aggregator-derived average instead of jumping straight to the static 2024 baseline — this is the core fix, replacing today's silent zero-swing behavior

### AC-3: Static 2024 baseline only fires when both sources are empty
- **Given** neither VoteHub nor the aggregator source has any usable data
- **When** the model computes its environment
- **Then** it falls back to `NATIONAL_PRES_MARGIN_2024_D` as today — this path still exists as a last resort, it's just no longer the second thing tried

### AC-4: Fallback state is visible in the API response
- **Given** any of the three paths above fired (VoteHub / aggregator / static baseline)
- **When** `GET /api/forecasts/congress` (and `/api/forecasts/model`) is called
- **Then** the response includes which source was actually used (e.g. a `swing_source` field: `"votehub"` \| `"aggregator"` \| `"fallback"`) — `swing_d: 0` must no longer be ambiguous between "genuinely no movement since 2024" and "no data, used the hardcoded number"

### AC-5: Frontend flags a fallback state, not just a live one
- **Given** `swing_source` is `"fallback"` in the API response
- **When** the model card renders
- **Then** it visibly indicates the number is not based on current polling (e.g. a label/tooltip) rather than presenting it with the same confidence as a live-data result
- **Given** `swing_source` is `"votehub"` or `"aggregator"`
- **When** the model card renders
- **Then** no fallback warning is shown — behaves as today

### AC-6: Market-consensus forecast is unaffected
- **Given** this fix only touches `_current_env()` / the in-house model path
- **When** `GET /api/forecasts/congress` is called
- **Then** the `dem_prob`/`rep_prob`/`sources` fields (Kalshi/Polymarket market consensus, top-level of each chamber) are byte-for-byte unchanged in their computation — this fix must not touch `_kalshi_source`/`_polymarket_source`

### AC-7: Tunable model endpoint (`/api/forecasts/model`) stays consistent
- **Given** the live-controls endpoint (`model_sim`) also calls `run_model`
- **When** it's called under any of the three environment-source scenarios
- **Then** it reflects the same `swing_source` behavior as `/congress` — no separate/divergent logic path

## Data Quality / Edge Cases
- Partial VoteHub data (some polls in-window, but all missing parseable `dem`/`rep`) must be treated as "no VoteHub signal" and fall through to the aggregator tier — not silently treated as a valid (but wrong) VoteHub average.
- If the aggregator data path requires a persistence change (per the feature plan's deferred question), that change must not alter the existing `/api/polls/generic-ballot` response shape or values — this fix adds a read path for the model, it doesn't change what the Polls page already shows.
- The three-tier fallback should not introduce a live network call (e.g. re-fetching Wikipedia) into the request path of `/api/forecasts/congress` — whatever data path is chosen, it must read already-ingested data, not fetch live, to avoid adding latency/fragility to a request that previously only touched the DB.

## Out of Scope
- Recalibrating `TAU`/`DELTA_HOUSE`/`DELTA_SENATE` or any Phase F backtesting.
- Changes to Kalshi/Polymarket market-consensus computation.
- General ingestion-health-style monitoring of *why* VoteHub's window went empty — this fix is about the model being resilient to it, not diagnosing the upstream cause each time.

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
