# Test Cases: Kalshi Markets Silently Stopped Ingesting

**Slug:** `kalshi-fetch-failure` &nbsp; **Source:** `02-acceptance-criteria.md`

## Coverage Map

| AC | Test IDs |
|---|---|
| AC-1 Total failure records failure | **TC-1** |
| AC-2 Partial failure | TC-2 |
| AC-3 Empty fetch never retires | **TC-3** |
| AC-4 Real retirement still works | TC-4 |
| AC-5 Markets ingesting | TC-5, TC-9 |
| AC-6 Forecast shows a market | TC-6, TC-10 |
| AC-7 Model untouched | TC-7 |
| AC-8 Filters unchanged | TC-8 |
| AC-9 Unavailable state | TC-11 |

## Backend

All respx-mocked against the existing harness; extend `test_kalshi_upsert.py`.

### TC-1 — Both series 403 → recorded failure (covers AC-1)
Mock both series returning 403. Run `refresh_kalshi`.
**Expected:** `SourceRun` for `kalshi_job` is `status: "failure"` with the error in `error_message`. **Not** success with `item_count: 0` — that is today's bug and the reason nobody noticed for a day.

### TC-2 — One series up, one down (covers AC-2)
CONTROLH returns markets, CONTROLS returns 503.
**Expected:** CONTROLH markets upserted; run records `success` with that count; a WARNING names CONTROLS.

### TC-3 — Failed fetch does not retire anything (covers AC-3)
Seed 4 active Kalshi markets. Mock both series failing. Run.
**Expected:** all 4 still `active = True`. Today's code flips all of them false via `notin_([])`.

### TC-4 — Successful fetch still retires a vanished market (covers AC-4)
Seed 5 active markets; mock a fetch returning 4 of them.
**Expected:** the absent one goes `active = False`, the other 4 stay active. Guards against fixing TC-3 by disabling retirement.

### TC-5 — Happy path upsert (covers AC-5)
Mock both series with realistic payloads (`volume_24h_fp` ~163000, `last_price_dollars` "0.8600").
**Expected:** 4 markets stored active with non-null `yes_price`; `item_count: 4`; one `MarketSnapshot` per market.

### TC-6 — Forecast exposes the market (covers AC-6)
With TC-5 state, call `/api/forecasts/congress`.
**Expected:** both chambers have a non-empty `sources` with `platform: "kalshi"` and non-null `dem_prob`.

### TC-7 — Model block unchanged (covers AC-7)
Diff the `model` block and `swing_source` against a pre-change fixture.
**Expected:** identical. Only market-derived fields move.

### TC-8 — Filters unchanged (covers AC-8)
Assert `MIN_VOLUME_24H == 1000.0` and `SERIES` keys are `CONTROLH`/`CONTROLS`. A dormant market at volume 14.24 is still excluded.

### TC-12 — Idempotency
Run the happy path twice.
**Expected:** still 4 `PredictionMarket` rows, no duplicates; snapshots accumulate one per run.

### TC-13 — Failure isolation
Kalshi fails; Polymarket run in the same cycle.
**Expected:** `markets_job` unaffected and still records its own success.

## Live verification (post-deploy)

### TC-9 — Real ingestion (covers AC-5)
After deploy, wait one cycle (10 min) and check `/api/status/sources`.
**Expected:** `kalshi_job` `success`, `item_count: 4`.

### TC-10 — Forecast page (covers AC-6)
Load the Polls page.
**Expected:** both chamber cards show a Kalshi probability beside the model. House market should be near 86% Dem, the value before the outage.

### TC-11 — Unavailable state, only if AC-9 applies (manual)
If Kalshi cannot be reached from Railway, force the no-source state.
**Expected:** the card says market data is unavailable. It must not present the in-house model's 96% alone with no explanation.

## Edge Cases & Failure Modes

- **Upstream down/malformed:** TC-1, TC-2. Malformed body (non-dict, `markets` not a list) takes the same path as a fetch error.
- **First run / empty table:** TC-5 from empty inserts cleanly.
- **Re-run:** TC-12.
- **Rate limit:** a 429 must retry with backoff, not be swallowed as success.
- **Reactivation:** rows currently sit `active = False`; the first good run must flip them back with no manual step.

## Regression Check

- `/api/markets` — Polymarket rows unchanged, Kalshi rows return
- `/api/forecasts/congress` — `swing_source` still `votehub`, model values unchanged
- Polls page `ForecastSection` and Dashboard `MarketsPanel`
- `/api/status/sources` — `kalshi_job` and `markets_job` both healthy
- Full suite green

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
