# Feature Plan: Fix In-House Forecast Model's Silent Swing Fallback

**Slug:** `forecast-model-swing-fallback-fix` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-21

## Problem / Goal
The in-house Congress forecast model (`backend/app/services/forecast_model.py`) is showing wildly stale results — House: 36% Dem / 64% Rep, median 214 Dem seats — while Kalshi (a real market) shows 83% Dem / 17% Rep for the same race. Confirmed via a live `GET /api/forecasts/congress` response: `"swing_d": 0`, which is not a coincidental small number — it's the literal fallback constant, meaning `_current_env()` fell through to the hardcoded 2024 baseline (`NATIONAL_PRES_MARGIN_2024_D`) with **zero live polling signal applied**, and nothing in the API response or UI indicates this happened.

Root cause: `_current_env()` (`forecast_model.py:62-69`) has exactly one data source — VoteHub polls tagged `poll_type="generic-ballot"`, inside a rolling 21-day window (`votehub.compute_average`, default `window_days=21`). This is a thin, single-source slice that can return `None` (e.g. a poll ages out of the window, or none of the in-window polls have parseable `dem`/`rep` fields) — at which point the model silently reverts to a static, non-current number. Meanwhile the Polls page shows a materially different, more robust signal: an average across 6 aggregators (5 scraped from Wikipedia's polling-average tables via `fetch_generic_ballot`, plus VoteHub's own), currently reading a stable D+4.9–5.0 — a real signal the model never sees.

Goal: make the model's environment estimate resilient to VoteHub's thin single-source window going empty, and make a fallback (if one ever fires) visible rather than silent.

## Context
- Touches Forecasting (per `SOURCES.md`) — specifically the in-house experimental model, not the market-consensus side (`_kalshi_source`/`_polymarket_source` in `forecasts.py`, which are unaffected and correct).
- Discovered live during Cowork roadmap planning (2026-07-21) — Samuel spotted the House model card looking dramatically out of sync with Kalshi, we traced it via the live API response.
- Related existing surfaces: `fetch_generic_ballot()` (`house_polls.py`) and `compute_average()` (`votehub.py`) already exist and are already combined for the Polls page (`polls.py`'s `/api/polls/generic-ballot`) — this fix reuses that existing combination rather than inventing a new one.

## Scope
- [x] Changed backend service: `_current_env()` in `forecast_model.py` — broaden its data source beyond VoteHub-only `compute_average` to also consider the Wikipedia-aggregator numbers from `fetch_generic_ballot()`, so a temporarily-empty VoteHub window doesn't zero out the whole environment estimate. Exact blend strategy (average of all available sources vs. VoteHub-primary-with-aggregator-fallback) to be settled in acceptance criteria/implementation plan.
- [x] Changed API contract: `ChamberModel` (`forecasts.py`) gains a visible indicator of whether the swing was computed from live data or fell back to the static baseline (e.g. a `swing_source` or `is_fallback` field) — currently `swing_d: 0` is indistinguishable from "genuinely zero swing" vs. "no data, used fallback," which is itself part of the bug.
- [x] Changed frontend: surface that indicator on the model card (even a small label/tooltip) so a stale/fallback state isn't presented with the same visual confidence as a real live estimate.
- [ ] Not deciding here: whether `fetch_generic_ballot()` needs to become an async dependency inside `run_model` (currently sync) — implementation plan should confirm whether this requires making `_current_env`/`run_model` async or whether a sync-cached read of already-ingested Wikipedia aggregator rows is sufficient (the data is already in some upserted form via the existing ingestion job, doesn't need a live fetch at request time — implementation plan should confirm exactly where that data lives at rest).

## Non-Goals
- Recalibrating `TAU`/`DELTA_HOUSE`/`DELTA_SENATE` or any other Phase F backtesting work — this is a data-input bug, not a model-calibration pass.
- Changing how the market-consensus (Kalshi/Polymarket) numbers are computed — those are already correct and unaffected.
- Building a general-purpose "data staleness" framework across all forecasting inputs (fundraising edges, incumbency, etc.) — scoped specifically to the generic-ballot environment input that's currently broken.
- Investigating why VoteHub's window happened to be empty at that specific moment (a `SourceRun`-style investigation) — out of scope here; `ingestion-health` (in progress) will make this kind of gap visible going forward for ingestion jobs generally, but this fix is about the model not being so fragile to it in the first place.

## Proposed Approach
Have `_current_env()` fall back through a priority chain instead of a single source: try VoteHub's own live average first (as today), and if that's unavailable, use the same aggregator-average logic the Polls page already computes (`fetch_generic_ballot()` + VoteHub, averaged) rather than jumping straight to the static 2024 baseline. Only fall to the hardcoded 2024 baseline if literally no polling data is available from either source — and when that happens, flag it explicitly in the model's output so it's visible in the API response and the UI, instead of looking identical to a confidently-computed live number.

## Open Questions / Risks
- **Deferred to Claude Code during implementation** (Samuel's call — this needs codebase-level verification neither of us can do from Cowork): `fetch_generic_ballot()` is currently an `async def` that hits Wikipedia's API live (`house_polls.py:243`) — calling it from `run_model` (invoked from a sync FastAPI route) needs either an async path through `forecasts.py`'s route, or reading already-ingested/cached aggregator data at rest instead of re-fetching live. First confirm whether the Wikipedia aggregator rows are persisted anywhere (check `models.py` for a matching table) or only ever returned transiently and merged at request time in `polls.py` — if not persisted, this fix may need a small persistence addition too, which would expand scope. Re-fetching Wikipedia live on every forecast request should be avoided if at all possible (wasteful, duplicates the existing scheduler job). Implementation plan should state which path was taken and why.
- Depends on nothing in-flight — independent of both `ingestion-health` (shipped, PR #9) and `write-endpoint-auth`, safe to queue whenever Claude Code is free, though flagged as higher-priority than either given it's producing a materially wrong public-facing number today.

## References
- Live bug confirmation: `GET https://<railway-backend>/api/forecasts/congress`, house block `"swing_d": 0`, captured 2026-07-21.
- `backend/app/services/forecast_model.py:62-69` (`_current_env`)
- `backend/app/services/votehub.py:279-322` (`compute_average`)
- `backend/app/services/house_polls.py:243-311` (`fetch_generic_ballot`)
- `backend/app/routers/polls.py:218-229` (existing combination pattern for `/api/polls/generic-ballot`, precedent for blending both sources)
