# Feature Plan: Staleness Labelling and Window Floor on Poll Averages

**Slug:** `poll-staleness-labels` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft (rev 2) &nbsp; **Date:** 2026-09-12

## Problem / Goal

`compute_average` (`app/elections/services/votehub.py`) is a sample-size-weighted mean
over polls whose fieldwork ended inside a rolling 21-day window measured from *now*.
The window is relative to today; the data is not. When an upstream feed stops
delivering, the window keeps advancing and drains itself, and nothing anywhere says so.

That is happening right now. VoteHub's approval stream is frozen upstream at fieldwork
**2026-08-28** — verified directly against `api.votehub.com/polls?poll_type=approval` on
both 09-11 and 09-12, 2,945 rows, newest unchanged. Our ingest runs hourly and is
healthy; there is simply nothing new to fetch. Their generic-ballot stream is current to
09-08, so this is the approval endpoint specifically.

The window drains on a known schedule:

| Date | Polls in window | Consequence |
|---|---|---|
| 2026-09-12 | 5 | Average shown as current, no date anywhere |
| 2026-09-14 | 5 | Four YouGov/Ipsos polls age out at end of day |
| **2026-09-16** | **1** | **Average silently becomes one pollster's number** |
| **2026-09-20** | **0** | **`compute_average` returns `None`; the card vanishes** |

**The 09-16 case is the damaging one.** The four polls ageing out average to roughly
net -21.7. The single survivor, TIPP Insights, is 38/52 — net **-14**. So on 16
September, displayed net approval jumps **+7.7 points** with no change in public
opinion whatsoever. It is pure window mechanics, and on a public site during an
election run-up it reads as news.

The 09-20 case is quieter but also wrong: `compute_average` returns `None`,
`VoteHubApprovalCard` hits `if (!avg) return null` on line 12, and the card disappears
from the Polls page with no explanation. No crash, no error, no trace.

## Context

- Touches **Politics & Polling**. Consumes `/api/votehub/approval` and
  `/api/votehub/generic-ballot`; renders through `VoteHubApprovalCard`,
  `ApprovalSection` and `GenericBallotBar`.
- Not an ingestion bug. `votehub_job` ran at 01:17 today and reported success. There is
  no fix available in `votehub.py`'s fetch path — the upstream feed is the constraint.
- Why now: an eight-day fuse. The spurious jump lands 16 September and the card
  disappears 20 September, both before the 13 October go/no-go and well before the
  election.
- Generic ballot has the identical exposure. It is current today (09-08 fieldwork, 6
  polls) purely because that stream is still being delivered. The same code path drains
  the same way the moment it stops, so fix both, not just the one that's bleeding.

## Scope

- [ ] New/changed data source — **no**
- [x] New/changed backend service — `compute_average` gains a minimum-poll floor and returns provenance
- [x] New/changed API route — `/api/votehub/approval` and `/api/votehub/generic-ballot` response shape grows (additive)
- [ ] New/changed scheduler job — **no**
- [ ] New/changed data model — **no, and no migration**
- [x] New/changed frontend — `VoteHubApprovalCard`, `ApprovalSection`, `GenericBallotBar`

## Non-Goals

- **Not adding a second approval source.** That's the durable fix for upstream silence
  and it deserves its own ticket (source selection, crosswalking, weighting). This
  ticket makes the existing number honest, which is the part with a deadline.
- **Not changing the weighting method, the 21-day window, or any returned average.**
  Deliberately: see Proposed Approach. Every number this ticket emits is identical to
  the number emitted today.
- Not touching `/api/polls/generic-ballot`, which merges VoteHub with the aggregator
  and is consumed by the forecast model. Out of scope entirely — see Risks.
- Not a visual redesign of the Polls page.

## Proposed Approach

**Revised 2026-09-12 after checking how real aggregators do this.** An earlier draft of
this plan proposed a minimum-poll floor that widens the window (21 → 30 → 45 → 60 days).
That is a workaround: it replaces one cliff with several smaller steps, and keeps the
underlying flaw. It is not what serious aggregators do, and — see below — it is not even
what VoteHub does with the same data.

**The standard is recency *weighting*, not a recency *cutoff*.** Every poll stays in;
its weight decays smoothly with age. An average built that way never empties, never
jumps when a poll crosses an arbitrary boundary, and degrades gracefully into "old and
uncertain" rather than "gone."

VoteHub publishes its own methodology and states it plainly: all polls weighted by
recency, weight declining smoothly as polls age, decay rate varying with polling volume
so that sparse questions fade older polls *more slowly* to reduce volatility. They also
down-weight pollsters who flood a race. We ingest their raw polls and then re-average
them with a cruder method than they apply to the same data — a hard 21-day cutoff,
`sqrt(sample_size)` weighting, no pollster quality, no house effects, and no protection
against one pollster dominating. (The current 5-poll window is 2 YouGov + 2 Ipsos.)

So this splits into two tickets, and **only the first has the 8-day fuse**:

### This ticket — make the number honest. No math changes.

1. `compute_average` returns provenance alongside today's fields:
   `newest_fieldwork_end`, `oldest_fieldwork_end`, and the `window_days` used. Purely
   additive; every existing field keeps its name, type and value.
2. Every card shows the newest fieldwork date. Past a threshold it carries a visible
   stale marker.
3. The empty state is explicit — "no polling in the last 21 days, most recent was
   28 Aug" — never a silent `return null`.
4. **Nothing in the weighting, the window length, or the returned averages changes.**
   That is what makes this safe to ship in a week: the forecast model's tier-1 input is
   numerically identical before and after.

This does not prevent the 16 September jump. It makes the jump legible — the card will
say it is built on one poll fielded 19 days ago, which is the truth, and a reader can
discount it accordingly.

### Follow-up ticket — replace the cutoff with decay weighting.

Own slug, own pipeline pass, no deadline. Removes the cliff entirely rather than
labelling it. **It changes returned averages, so it changes `_current_env()`'s tier-1
input and therefore chamber forecasts** — that impact needs measuring and reviewing
deliberately, which is precisely why it must not ride along with an urgent labelling fix.

Worth considering in that ticket: whether to re-average at all, or ingest VoteHub's own
published average and keep local computation as a fallback. They compute it better than
we do. The counter-argument is that it deepens dependence on a feed that is, right now,
15 days stale.

## Open Questions / Risks

- **Staleness threshold.** 10 days is a judgement call, not a finding. Approval polling
  normally arrives weekly, so 10 days is genuinely unusual; generic ballot is slower and
  may want a different threshold. Possibly per-poll-type.
- **Does labelling alone clear the 16 September bar?** It does not stop the +7.7 point
  apparent jump, only explains it. If that is unacceptable on a public page, the
  alternatives are to hide the card below a minimum poll count, or to pull the decay
  follow-up forward and accept the forecast-model review inside the fuse. Samuel's call.
- **Regression risk — `/api/polls/generic-ballot` and the forecast model.** This is the
  one to be careful about. `_current_env()` in the forecast model reads a VoteHub live
  average as tier one of its three-tier fallback (PR #11). If this ticket changes what
  that path returns, chamber forecasts move. **Requirement: the forecast model's input
  must be unchanged by this ticket**, or the change must be deliberate and separately
  reviewed. Confirm which function the model actually calls before touching
  `compute_average`.
- **Additive response only.** Existing fields keep their names and meanings so nothing
  in the frontend breaks on deploy.
- No upstream stability risk — this ticket adds no upstream dependency.

## References

- `docs/ROADMAP.md` item #11
- `docs/features/forecast-model-swing-fallback-fix/` — PR #11, the three-tier fallback this must not disturb
- `app/elections/services/votehub.py` — `compute_average`
- `frontend/src/components/VoteHubApprovalCard.tsx` line 12 — the silent `return null`
