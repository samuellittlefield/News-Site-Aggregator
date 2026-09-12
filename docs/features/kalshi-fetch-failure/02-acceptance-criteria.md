# Acceptance Criteria: Kalshi Markets Silently Stopped Ingesting

**Slug:** `kalshi-fetch-failure` &nbsp; **Source:** `01-feature-plan.md`

## Criteria

### AC-1: A total fetch failure records as a failure
- **Given** every series in `SERIES` fails to fetch (non-2xx, timeout, or unparseable body)
- **When** `refresh_kalshi` runs
- **Then** the `SourceRun` row for `kalshi_job` records `status: "failure"` with the upstream error in `error_message` — never `success` with `item_count: 0`

### AC-2: A partial failure still records what it got
- **Given** one series fetches successfully and the other fails
- **When** `refresh_kalshi` runs
- **Then** the successful series' markets are upserted, the run records `success` with that count, and the failure is logged at WARNING with the series named

### AC-3: An empty fetch never retires existing markets
- **Given** `seen_ids` is empty because no market was processed
- **When** the retirement block runs
- **Then** it is a no-op. No `PredictionMarket` row has `active` flipped to `False`. Retirement is meaningful only relative to a fetch that actually returned markets

### AC-4: A genuine disappearance still retires correctly
- **Given** a successful fetch that returns markets, one previously-stored ticker now absent
- **When** the retirement block runs
- **Then** that one market is set `active = False` and the returned ones stay active — AC-3 must not break real retirement

### AC-5: Markets are ingesting again
- **Given** the connection fix is deployed
- **When** `kalshi_job` next runs
- **Then** `CONTROLH-2026-D`, `CONTROLH-2026-R`, `CONTROLS-2026-D` and `CONTROLS-2026-R` are stored `active` with non-null `yes_price`, and `kalshi_job` records `item_count: 4`

### AC-6: The forecast cards show a market again
- **Given** markets are ingesting
- **When** `/api/forecasts/congress` is called
- **Then** both chambers return a non-empty `sources` array with `platform: "kalshi"` and a non-null `dem_prob`

### AC-7: The in-house model is untouched
- **Given** this ticket changes no model code
- **When** `/api/forecasts/congress` is called
- **Then** `swing_d`, `swing_source` and each chamber's `model` block are unchanged. Only the market-derived fields move

### AC-8: Volume and series filters are unchanged
- **Given** `MIN_VOLUME_24H = 1000.0` and the two series tickers
- **When** the fix lands
- **Then** both are unchanged. Live volume is ~163k-178k, so the filter is not implicated and loosening it would mask the real cause and admit dormant 2028 markets

### AC-9: If the block cannot be worked around, the UI says so
- **Given** Kalshi cannot be reached from Railway at all
- **When** the forecast card renders with no market source
- **Then** it shows an explicit "market data unavailable" state rather than quietly presenting the in-house model alone. A 96% model probability with no market beside it and no explanation is the outcome to avoid

## Data Quality / Edge Cases

- **Upsert idempotency unchanged** — re-running must not duplicate `PredictionMarket` rows or double-write `MarketSnapshot`.
- **Failure isolation unchanged** — a Kalshi failure must not affect `markets_job` (Polymarket), which is currently healthy at 60 items.
- **Rate limits:** Kalshi's public read endpoints allow roughly 30 req/s; this job makes two requests per run, so throttling is unlikely but a 429 must be retried with backoff rather than swallowed.
- **Snapshot retention** (`SNAPSHOT_RETENTION_DAYS = 30`) is unchanged, and its delete must not run destructively on a failed fetch either.
- **First run after the outage:** markets currently sit `active = False`. The fix must reactivate them via the normal upsert, not require manual intervention.

## Out of Scope

- Adding or replacing a market source
- Generic `SourceRun` staleness detection (roadmap #13)
- Any change to the in-house forecast model
- Polymarket

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
