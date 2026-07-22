# Implementation Plan: Fix In-House Forecast Model's Silent Swing Fallback

**Slug:** `forecast-model-swing-fallback-fix` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Add a small persisted table for the Wikipedia-sourced generic-ballot aggregator rows (currently fetched live and discarded inside `refresh_house_polls`), have `_current_env()` fall through VoteHub → that stored aggregator average → static 2024 baseline instead of jumping straight to the baseline, and surface which tier fired via a new `swing_source` field on the API response and model card.

**Resolves the feature plan's deferred question:** the aggregator rows are *not* currently persisted anywhere — `fetch_generic_ballot()` is called live from two places (`polls.py`'s `/api/polls/generic-ballot` route, and `refresh_house_polls`, which discards the result). Rather than making the model call Wikipedia live (rejected per AC edge cases) or restructuring the Polls page's existing live-fetch behavior (out of scope, would risk changing `/api/polls/generic-ballot`'s response), the fix persists the same data `refresh_house_polls` is already fetching on its normal 6h cadence, giving the model a DB-only read path. The Polls page's route is untouched.

## Backend Changes
*(Python 3.9 — use `Optional[...]`, not `X | Y`)*

| File | Change |
|---|---|
| `backend/app/models.py` | New `GenericBallotAggregate` model: `id` (PK), `source` (String, unique — upsert key, mirrors `ServiceStatus`'s upsert-by-name pattern), `rep` (Float), `dem` (Float), `fetched_at` (DateTime). One current row per aggregator source, not a history log — matches the feature's "current state" need, no reason to grow unbounded |
| `backend/alembic/versions/` | New migration, revises current head. Additive-only (new table) |
| `backend/app/services/house_polls.py` | `refresh_house_polls` (line ~685-690): after `generic = await fetch_generic_ballot(db)`, upsert each row into `GenericBallotAggregate` by `source` before returning — same function, same cadence, no new scheduler job. Wrap the upsert in its own try/except so a persistence hiccup can't break the existing district-poll refresh in the same function (consistent with this codebase's failure-isolation convention) |
| `backend/app/services/forecast_model.py` | `_current_env()` (line 62-69) becomes a three-tier lookup: (1) `votehub.compute_average(db, "generic-ballot")` as today; (2) if `None`, query `GenericBallotAggregate` and compute a simple mean of `dem`/`rep` across all stored rows (no sample-size weighting available for these aggregator averages, unlike VoteHub's raw polls); (3) if that's also empty, `NATIONAL_PRES_MARGIN_2024_D`. Returns `(margin, source_tag)` instead of just `margin` — `source_tag` is `"votehub"` \| `"aggregator"` \| `"fallback"` |
| `backend/app/services/forecast_model.py` | `run_model()`: thread `source_tag` through into `_summary()`'s returned dict as `swing_source`, alongside the existing `swing_d` |
| `backend/app/routers/forecasts.py` | `ChamberModel` gains `swing_source: str`; `_chamber_model()` reads it off `block["swing_source"]` |

No changes to `_kalshi_source`, `_polymarket_source`, or anything in the top-level `dem_prob`/`rep_prob` market-consensus computation (AC-6).

## Frontend Changes
| File | Change |
|---|---|
| `frontend/src/api/client.ts` | Extend whatever type represents `ChamberModel` with `swing_source: string` |
| Model card component (wherever `ChamberModel` is currently rendered — locate via the existing forecast card, likely in `PollsPage.tsx` or a dedicated forecast component) | When `swing_source === "fallback"`, show a visible label/tooltip (e.g. "no current polling data — showing 2024 baseline") instead of presenting the number with the same visual weight as a live estimate. No change when `swing_source` is `"votehub"` or `"aggregator"` |

## Data Model / Migration Notes
- `GenericBallotAggregate` is upsert-by-`source` (one current row per aggregator), consistent with the feature plan's non-goal of building a history/logging table — this only needs to answer "what's the latest known aggregator average," not track it over time.
- Migration is additive-only, empty table until the next `refresh_house_polls` run (every 6h) populates it — until then, tier 2 simply has no rows and falls through to tier 3, same as today, so there's no broken intermediate state.
- No backfill needed or possible (data wasn't stored before this fix).

## Sequencing
1. Migration: `GenericBallotAggregate` table
2. `house_polls.py`: persist aggregator rows inside `refresh_house_polls`
3. `forecast_model.py`: three-tier `_current_env()`, thread `swing_source` through `run_model`
4. `forecasts.py`: `swing_source` on `ChamberModel`
5. Frontend: type + model-card fallback indicator
6. Tests (per `04-test-cases.md`)

## Documentation Updates
- [ ] `SOURCES.md` — note that the generic-ballot aggregator data (Wikipedia, via `fetch_generic_ballot`) is now also persisted into `GenericBallotAggregate` as a side effect of `refresh_house_polls`, for the forecast model's use — brings this fetch back in line with the repo's usual fetch → persist → route/consume convention, which it was missing before this fix
- [ ] `.env.example` — not needed, no new env vars

## Risks / Rollback
- Additive migration, trivial rollback (`alembic downgrade`, no data loss — nothing existing reads or depends on the new table yet).
- Main risk is the mean-across-aggregators computation (tier 2) being a weaker signal than VoteHub's sample-size-weighted average (tier 1) — acceptable since it only fires when tier 1 is empty, and is still far better than the static-baseline status quo bug being fixed.
- Low blast radius: changes are scoped to `_current_env()`, `run_model()`'s output dict, and one insert inside an existing, already-isolated service function — nothing in the market-consensus or other-source ingestion paths is touched.

## Test Plan Pointer
See `04-test-cases.md`. All backend cases automatable via `backend/tests/`'s pytest harness (`client`/`db` fixtures, respx for any mocked HTTP).
