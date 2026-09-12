# Implementation Plan: Staleness Labelling on Poll Averages

**Slug:** `poll-staleness-labels` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

Add two provenance fields to `compute_average`'s return, thread them to three
components, and replace one silent `return null` with a real empty state. Deliberately
small: no math changes, so the forecast model cannot move.

## Backend Changes

*(Keep `Optional[...]` over `X | Y`.)*

| File | Change |
|---|---|
| `app/elections/services/votehub.py` | `compute_average` adds `newest_fieldwork_end` and `oldest_fieldwork_end` to both the approval and generic-ballot return dicts. **Do not touch** the `cutoff` computation, the `weighted()` helper, `window_days`, or any existing key |
| `app/elections/routers/votehub.py` | Response model gains the two optional fields. No logic change |
| `app/elections/services/forecast_model.py` | **No change.** Line 80 reads only `gb["margin"]`; additive keys are invisible to it |
| `app/elections/routers/polls.py` | **No change.** Imports `compute_average` as `compute_votehub_average`; additive keys are ignored |
| `SOURCES.md` | Document the window-drain → tier-2 fallback exposure (AC-10) |

There are exactly three consumers of `compute_average` — `routers/votehub.py`,
`routers/polls.py` and `services/forecast_model.py`. Additive-only is what keeps two of
them untouched.

## Frontend Changes

| File | Change |
|---|---|
| `src/api/client.ts` | Extend the average type with the two optional fields |
| `src/components/VoteHubApprovalCard.tsx` | Show newest fieldwork date; stale marker; emphasize thin poll counts; **replace line 12's `if (!avg) return null`** with the explicit empty state |
| `src/components/ApprovalSection.tsx` | Same labelling treatment |
| `src/components/GenericBallotBar.tsx` | Same labelling treatment |

Put the threshold logic and the label/marker in one small shared helper rather than
three copies — `classify()` in `SourceHealthSection` is the precedent from PR #12 for a
shared classifier both surfaces call.

**Threshold:** 10 days, as a named constant in one place so it's trivially tunable. Not
derived from anything; it's a judgement call the plan flags as such.

## Data Model / Migration Notes

None. No model, column, or upsert change. No migration.

## Sequencing

1. **Capture the baseline first.** Save current `/api/votehub/approval`,
   `/api/votehub/generic-ballot` and `/api/forecasts/congress` responses as fixtures.
   AC-2 and AC-3 are diffs against these — without them there's nothing to prove.
2. Backend: add the two fields. Run the baseline diff. Existing keys must be identical.
3. Backend tests for AC-1, AC-2, AC-3.
4. `client.ts` type extension.
5. Shared threshold helper.
6. The three components, empty state last.
7. `SOURCES.md` note.

## Documentation Updates

- [ ] `SOURCES.md` — the drain → tier-2 exposure (AC-10)
- [ ] `.env.example` — nothing new
- [ ] `docs/ROADMAP.md` — item #11 → shipped with PR link; add the decay-weighting follow-up as a new `idea` row

## Risks / Rollback

- **Rollback is `git revert`.** No migration, no data change.
- **The only real risk is touching the math while in `compute_average`.** The function is
  small and the temptation to "fix the window while I'm here" is the exact failure mode
  this ticket is scoped to avoid. AC-3's forecast diff is the guard.
- **Second risk: an empty state that throws.** AC-8 covers a genuinely empty table, where
  there's no date to name. Don't reach for `polls[0]` without a length check.
- Frontend has no Vitest, so the component cases are manual click-through.

## Test Plan Pointer

See `04-test-cases.md`.
