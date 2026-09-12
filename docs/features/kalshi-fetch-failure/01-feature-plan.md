# Feature Plan: Kalshi Markets Silently Stopped Ingesting

**Slug:** `kalshi-fetch-failure` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-09-12

## Problem / Goal

`/api/forecasts/congress` returns `sources: []` and `dem_prob: null` for both chambers.
Zero Kalshi markets are stored. On 2026-09-11 there were 4, with the House market at
86% Dem. `kalshi_job` ran at 02:37 on 09-12 and recorded **`status: success`,
`item_count: 0`, no error**.

The live consequence: the Polls page forecast section now shows the in-house
experimental model asserting **96.2% Dem for the House** with no market number beside
it. Kalshi was the guaranteed market source and the sanity check on that model — which
is exactly the failure mode PR #11 was built to expose in July, reappearing one layer
out.

## Context

- Touches **Forecasting**. `app/elections/services/kalshi.py` → `PredictionMarket`
  (platform `kalshi`) + `MarketSnapshot` → `/api/markets` and
  `/api/forecasts/congress` → `ForecastSection` on the Polls page.
- Polymarket (`markets_job`) is healthy at 60 items, so this is Kalshi-specific, not a
  shared markets-table problem.

### Diagnosis, from evidence gathered 2026-09-12

**Upstream is fine.** Running the service's exact query by hand returns qualifying data:

```
GET external-api.kalshi.com/trade-api/v2/markets?series_ticker=CONTROLH&status=open&limit=50
  CONTROLH-2026-D | volume_24h_fp 163,023.54 | last_price_dollars 0.8600
  CONTROLH-2026-R | volume_24h_fp 178,402.37 | last_price_dollars 0.1400
```

Both clear `MIN_VOLUME_24H = 1000.0` by two orders of magnitude and carry real prices.
The `status=open` parameter works despite the markets reporting `status: "active"`.

**So the fetch fails from Railway, not from the query.** The most probable path, and the
first thing to check:

```python
except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
    logger.warning("Kalshi fetch failed (%s): %s", series_ticker, e)
    continue                                    # kalshi.py:78-80
```

A 403, 429 or 451 from Kalshi raises `HTTPStatusError`, which is caught **inside**
`fetch_kalshi`, logged at WARNING, and `continue`s. Both series are skipped, `saved`
stays 0, the function returns 0, and the scheduler wrapper — which only sees a clean
return — records **success**. A total upstream failure is indistinguishable from a quiet
day. Railway logs will contain `Kalshi fetch failed` if this is right.

**Why the existing rows disappeared rather than just going stale.** When the loop saves
nothing, `seen_ids` is empty, and the retirement block runs:

```python
PredictionMarket.market_id.notin_(seen_ids)     # kalshi.py:134
```

`notin_([])` against an empty set does not exclude anything, so **every** existing Kalshi
market is flipped to `active = False`. One failed fetch retires the whole platform.

**Revising an earlier suspicion.** My first read was that PR #14 (the T1 seam refactor,
merged 09-11) had broken this, on timing. That now looks unlikely: `kalshi.py`'s
imports resolve correctly, its logic is unchanged, and its scheduler wrapper is
identical in shape to Polymarket's working one. A Kalshi-side block on the datacenter IP
or the `SituationMonitor/1.0` User-Agent explains the evidence better, and the timing is
probably coincidence. **Code should confirm from logs rather than inherit either guess.**

## Scope

- [ ] New data source — no
- [x] `app/elections/services/kalshi.py` — surface fetch failure; fix the empty-`seen_ids` retirement
- [x] `app/scheduler.py` — `refresh_kalshi` must be able to record failure
- [ ] New API route — no
- [ ] Data model / migration — **no**
- [ ] Frontend — no, beyond whatever restoring the data fixes on its own

## Non-Goals

- Not replacing Kalshi or adding a third market source.
- Not changing `MIN_VOLUME_24H`, the series tickers, or the price-parsing quirks.
- Not the generic `SourceRun` staleness work (roadmap #13) — that is the systemic
  version of this and stays its own ticket. This one fixes the specific live outage.
- Not touching Polymarket, which is working.

## Proposed Approach

1. **Diagnose from production logs first.** Confirm whether `Kalshi fetch failed`
   appears and with what status code. Everything below assumes it does; if the logs say
   otherwise, follow the evidence and say so.
2. **A total fetch failure must record as a failure.** If every series in `SERIES` fails
   to fetch, `fetch_kalshi` must raise or otherwise signal, so `refresh_kalshi`'s
   `except` records `_record_failure`. A partial failure — one series up, one down —
   should still record success with the count it got, plus a warning. The principle:
   *found nothing because there was nothing* and *found nothing because we could not
   ask* must not look identical.
3. **Never retire everything on an empty fetch.** Guard the retirement block so it is a
   no-op when `seen_ids` is empty. Retiring markets is only meaningful relative to a
   successful fetch.
4. **Restore the connection.** Depending on the status code: a more conventional
   User-Agent, a retry with backoff on 429, or the alternate host
   `api.elections.kalshi.com`, which also serves these markets. Note that host returns
   `yes_bid`/`last_price` as nulls where `external-api` returns populated
   `*_dollars` fields, so it is not a drop-in — verify field shape before switching.

## Open Questions / Risks

- **Is it a block, a rate limit, or something else?** Determines the fix. Logs decide.
- **If Kalshi is blocking datacenter IPs**, there may be no clean fix from Railway. In
  that case the honest outcome is a visible "market data unavailable" state on the
  forecast card rather than a silently absent comparison — worth surfacing to Samuel
  rather than engineering around.
- **Regression risk is low but real:** `/api/forecasts/congress` currently degrades to
  model-only. Restoring markets changes what the page shows — that is the point, but the
  chamber `dem_prob` values will move from `null` back to market numbers, and anything
  downstream expecting `null` should be checked.
- **Do not "fix" this by loosening `MIN_VOLUME_24H`.** The evidence shows volume is
  fine; that would mask the real cause and let 2028 dormant markets in.

## References

- `docs/features/forecast-model-swing-fallback-fix/` — PR #11, the same silent-degradation class
- `docs/features/ingestion-health/` — `SourceRun` semantics this ticket sharpens
- `app/elections/services/kalshi.py` lines 78-80 (swallowed failure), 133-137 (retirement)
- `docs/ROADMAP.md` item #13 — the systemic version of this problem
