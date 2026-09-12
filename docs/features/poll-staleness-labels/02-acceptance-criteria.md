# Acceptance Criteria: Staleness Labelling on Poll Averages

**Slug:** `poll-staleness-labels` &nbsp; **Source:** `01-feature-plan.md` (rev 2)

## Criteria

### AC-1: Every returned average carries its own provenance
- **Given** polls in the database for a poll type
- **When** `/api/votehub/approval` or `/api/votehub/generic-ballot` is called
- **Then** the `average` object includes `newest_fieldwork_end` and `oldest_fieldwork_end` (ISO dates of the max/min `end_date` actually averaged) alongside the existing `window_days` and `n_polls`

### AC-2: Existing fields are numerically identical
- **Given** the same database state before and after this change
- **When** both versions of `compute_average` run
- **Then** `approve`, `disapprove`, `net`, `dem`, `rep`, `margin`, `n_polls` and `window_days` are **byte-identical**. The change is purely additive

### AC-3: The forecast model is unaffected
- **Given** `forecast_model.py` line 80 calls `compute_average(db, "generic-ballot")` directly and reads `gb["margin"]` as tier-1 swing
- **When** `/api/forecasts/congress` is called before and after
- **Then** `swing_d`, `swing_source`, `dem_prob`, `rep_prob` and `median_dem_seats` are unchanged for both chambers. **This is the hard gate on the ticket**

### AC-4: Newest fieldwork date is visible on every average
- **Given** an average rendered on the Polls page
- **When** a reader looks at the approval card, the generic ballot bar, or `ApprovalSection`
- **Then** the newest fieldwork date is shown without interaction — no hover, no click

### AC-5: Stale averages are visibly marked
- **Given** an average whose `newest_fieldwork_end` is more than the staleness threshold old
- **When** it renders
- **Then** it carries a visible stale marker distinguishable from the normal state by more than color alone

### AC-6: Thin averages say so
- **Given** an average built from fewer than 3 polls
- **When** it renders
- **Then** the poll count is visibly emphasized rather than shown as ordinary small print. On 2026-09-16 the approval card will be a single poll fielded 19 days earlier, and a reader must be able to see that without reading the fine print

### AC-7: The empty state is explicit, never silent
- **Given** zero polls inside the window, so `compute_average` returns `None`
- **When** the card renders
- **Then** it shows an explicit no-recent-polling state naming the most recent fieldwork date on record. It must **not** `return null` and disappear, which is today's behaviour at `VoteHubApprovalCard.tsx` line 12

### AC-8: The empty state survives a genuinely empty table
- **Given** no rows at all for that poll type (not merely none in window)
- **When** the card renders
- **Then** it shows a first-run empty state without throwing, and without inventing a date

### AC-9: Both poll types are covered
- **Given** approval and generic ballot share `compute_average`
- **When** either drains or goes stale
- **Then** both surfaces behave identically. Generic ballot is healthy today at 4 days only because that stream is still delivering

### AC-10: Window drain is recorded as a forecast risk
- **Given** that if generic ballot ever drains to zero, `compute_average` returns `None` and `_current_env` silently drops to tier 2 (aggregator)
- **When** this ticket ships
- **Then** that exposure is documented in `SOURCES.md` or the forecast model's docstring. No code change required here — PR #11 already makes the tier visible — but the drain mechanism as a *trigger* must be written down

## Data Quality / Edge Cases

- **Upstream silence is the normal case here, not an exception.** VoteHub approval has been frozen at 2026-08-28 since at least 09-11. The feature must behave correctly during indefinite upstream silence.
- **No ingestion, upsert or model change**, so idempotency and failure isolation are untouched.
- **Timezone:** `end_date` is stored tz-aware UTC; `compute_average`'s cutoff uses `datetime.now(timezone.utc)`. Date arithmetic for labels must not shift a date by a day in the user's locale.
- **No new upstream dependency**, so no rate-limit or auth surface.

## Out of Scope

- Any change to weighting, window length, or returned average values
- Decay-weighted averaging (follow-up ticket — it *does* move forecasts)
- A second approval source
- Pollster-quality weighting, house effects, or per-pollster down-weighting
- Hiding the card below a minimum poll count — considered and declined; Samuel chose to fail forward and let 09-16 happen visibly
- District poll data quality (`district-poll-data-quality`, roadmap #12)

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
