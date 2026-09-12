# Implementation Plan: Kalshi Markets Silently Stopped Ingesting

**Slug:** `kalshi-fetch-failure` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

Diagnose from production logs, restore the connection, and close the two defects that
turned an upstream outage into silent data loss: a swallowed fetch error reported as
success, and an empty-`seen_ids` retirement that deactivated every stored market.

## Backend Changes

*(Keep `Optional[...]` over `X | Y`.)*

| File | Change |
|---|---|
| `app/elections/services/kalshi.py` | Track per-series fetch outcomes. Raise (or return a sentinel the wrapper can detect) when **all** series fail, so AC-1 records a failure. Guard the retirement block on non-empty `seen_ids` (AC-3). Apply whatever connection fix the logs justify |
| `app/scheduler.py` | `refresh_kalshi` records failure on the all-failed signal. Wrapper shape otherwise unchanged |
| `SOURCES.md` | Update the Kalshi row if the host or headers change |
| `backend/tests/test_kalshi_upsert.py` | Extend — it exists and passes today, which is why CI did not catch this |

### Order of investigation

1. **Read Railway logs for `Kalshi fetch failed`.** Note the status code. Everything
   else follows from it.
2. 403 or 451 → a block. Try a conventional browser User-Agent first, then
   `api.elections.kalshi.com`. **That host returns `yes_bid`/`last_price` as nulls where
   `external-api` returns populated `*_dollars` fields — confirm field shape before
   switching or you will trade an outage for silent null prices.**
3. 429 → retry with backoff.
4. Neither → the hypothesis is wrong. Stop, write up what the logs actually say.

### The two defects, independent of the connection fix

Both are worth fixing regardless of what the logs say, because they are what made an
upstream problem invisible:

- **Swallowed failure.** `kalshi.py:78-80` catches `HTTPStatusError`, logs WARNING,
  `continue`s. With both series failing the function returns 0 and the wrapper records
  success. Distinguish "asked, got nothing" from "could not ask."
- **Empty-set retirement.** `kalshi.py:134` `notin_(seen_ids)` with `seen_ids` empty
  excludes nothing and flips every Kalshi market inactive. One failed fetch retires the
  platform.

## Frontend Changes

None required if the connection is restored. If AC-9 applies — Kalshi unreachable from
Railway — then `ForecastSection` needs an explicit market-unavailable state. Check with
Samuel before building that; it changes the scope.

## Data Model / Migration Notes

None. No model, column or migration change. Existing rows are `active = False` and the
normal upsert reactivates them.

## Sequencing

1. Read the logs. Record the status code in the PR description.
2. Fix the empty-`seen_ids` retirement (AC-3/AC-4) — smallest, safest, independent.
3. Fix the swallowed failure (AC-1/AC-2).
4. Apply the connection fix.
5. Verify live: `kalshi_job` records `item_count: 4`; `/api/forecasts/congress` shows
   `sources` for both chambers.
6. Extend `test_kalshi_upsert.py`.

## Documentation Updates

- [ ] `SOURCES.md` — Kalshi row, if host or headers changed
- [ ] `.env.example` — nothing new expected
- [ ] `docs/ROADMAP.md` — new item #15 → shipped with PR link

## Risks / Rollback

- **Rollback is `git revert`.** No migration, no data change.
- **Do not loosen `MIN_VOLUME_24H`** to make markets appear. Volume is ~163k-178k; the
  filter is not the problem and loosening it admits dormant 2028 markets.
- **The alternate host is not a drop-in** — different price field shape. Switching
  without checking trades a visible outage for silent null prices, which is worse.
- **AC-3 must not break real retirement** (AC-4). Guard on emptiness, don't delete the
  block.
- **Do not adjust the in-house model** to compensate for a missing market. Untouched.

## Test Plan Pointer

See `04-test-cases.md`.
