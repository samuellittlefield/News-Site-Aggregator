# Feature Plan: Teach `SourceRun` the Difference Between Quiet and Broken

**Slug:** `sourcerun-staleness` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft (rev 2 — backend only) &nbsp; **Date:** 2026-09-12

## Problem / Goal

A source that runs on schedule and produces nothing is indistinguishable from a healthy
one. `classify()` in `SourceHealthSection.tsx` has four states — `ok`, `stale`,
`failure`, `never_run` — and `stale` only means *the job hasn't run recently*:

```ts
if (minutesSince(s.last_success_at) > s.cadence_minutes) return "stale";
return "ok";
```

A job that fires every ten minutes and returns zero items forever is `ok` on every run.

**This has now cost us twice in two days, and both times a human had to find it:**

- **Economist/YouGov** (#10) — discovery broken for **46 days**, recording
  `success`/`item_count: 0` every 12 hours. Found by comparing fieldwork dates against
  upstream by hand.
- **Kalshi** (#15) — a transient fetch failure, swallowed inside `fetch_kalshi`, recorded
  as `success`/`item_count: 0`, which then retired every stored market via an empty
  `seen_ids`. Found by noticing the forecast cards had lost their market comparison.

Neither appeared on the Data Sources panel. The panel's job is to be the thing that
notices, and on the two occasions that mattered it noticed nothing.

## Context

- Touches **Service Status** (cross-cutting). `SourceRun` +
  `app/shared/services/source_run.py` → `GET /api/status/sources` →
  `SourceHealthSection` on the Admin page.
- Builds directly on `ingestion-health` (PR #9), which established the row and
  `SOURCE_CADENCE`, and on `status-admin-consolidation` (PR #12), which exported
  `classify()` and `summarizeSourceHealth()` as the single classifier.
- Why now: the two incidents above, and a public launch before November. The cost of a
  silent feed is much higher once strangers are reading the numbers.

### Two findings that shape the design

**1. `item_count` does not mean the same thing across jobs.** `refresh_votehub` records
`item_count=house` — only the House district poll count — and discards `counts` from
`fetch_votehub_polls`, which is what stores approval and generic ballot. So
`votehub_job` reports `items=0` while the approval and generic-ballot data it just
refreshed is current. Any rule keyed on `item_count` inherits that inconsistency.

**2. Zero is legitimate for some sources.** `issue_tagger_job` runs weekly and correctly
returns 0 when no candidates are pending. `economist_job` runs every 12 hours but new
reports appear roughly weekly, so most runs *should* return 0. A fixed multiple of
`cadence_minutes` would flag both constantly, and an alerting surface that cries wolf is
worse than none — people stop reading it, which is how you get 46 days.

So the expectation has to be **declared per source**, not derived from cadence.

## Scope

- [ ] New data source — no
- [x] `app/shared/services/source_run.py` — record when a run actually produced something; per-source data-freshness expectation
- [x] `app/scheduler.py` — fix `refresh_votehub`'s `item_count`; no other job logic changes
- [x] `GET /api/status/sources` — response grows (additive)
- [x] `backend/app/models.py` — one nullable column on `SourceRun` + **Alembic migration**
- [ ] Frontend — **none.** See the rescope note below

## Rescoped 2026-09-12: backend only

The first draft added a fifth `quiet` state to `classify()` plus a palette entry, a card
treatment and a banner count. That is cut, for three reasons that only became clear after
writing it:

1. **The panel is a one-reader surface.** Samuel is the only person who will ever open it.
2. **It is currently public** — `GET /api/status/sources` has no auth and `/admin` is
   reachable by URL, so the new state would have been publicly visible. That gap is now
   roadmap #16 and is a launch blocker in its own right.
3. **The 46-day Economist failure was a nobody-was-looking failure, not a rendering
   failure.** A better badge would not have caught it. Nothing opened the page.

So the detection logic moves to where it is useful to *every* reader: the route computes
a `data_state` and returns it. Reading the JSON directly answers the question today; a
panel, a digest, or an alert can consume the same field later without recomputing it.

Alerting is deliberately still out — with zero traffic it is heavy-handed, and it is a
separate decision once the product has readers.

## Non-Goals

- **No alerting, email or push.** Deferred deliberately — zero traffic makes it
  heavy-handed today.
- **No frontend change at all.** See the rescope note.
- Not tracking the freshness of the *data's own* timestamps (a poll's fieldwork date, an
  article's publish date). That is per-source and much larger; #11 did it for poll cards
  specifically. This ticket tracks whether a source is *producing* at all.
- Not changing any `fetch_*` function's behaviour, cadence, or upstream.
- Not fixing any individual broken source — #15 is its own ticket.
- Not a redesign of the Admin page.

## Proposed Approach

**1. Record when a run last produced something.** Add `last_nonempty_at` to `SourceRun`,
set by `record_success` whenever `item_count` is greater than zero. It parallels
`last_success_at` exactly — "the last time this actually worked" versus "the last time
this actually produced" — and needs no counter or reset logic.

**2. Declare an expectation per source.** Add `expected_data_interval_minutes` to the
registry entry alongside `label` and `cadence_minutes`: how long this source may
plausibly go without producing anything before that is a problem. `None` means exempt,
for sources where zero is routine.

Starting values, to be argued with rather than accepted:

| Source | Cadence | Expected data interval | Why |
|---|---|---|---|
| `kalshi_job` | 10 min | 1 hour | Should return 4 markets every single run |
| `markets_job` | 10 min | 1 hour | Same |
| `earthquakes_job` | 5 min | 6 hours | M2.5+ somewhere on Earth is near-continuous |
| `economist_job` | 12 h | 14 days | New reports appear ~weekly; 46 days was the failure |
| `house_polls_job` | 6 h | 21 days | District polls are sporadic even in season |
| `votehub_job` | 1 h | 7 days | After the `item_count` fix below |
| `issue_tagger_job` | weekly | `None` | Zero is the correct answer with nothing pending |

**3. The route computes the verdict.** `GET /api/status/sources` returns a `data_state`
per source: `producing`, `quiet`, `exempt`, or `unknown` (no `last_nonempty_at` yet).
Computing it server-side means curl, a future panel, and a future digest all agree
without reimplementing the rule. `classify()` is untouched — the panel keeps rendering
exactly what it renders today and can pick the field up whenever it is worth doing.

**4. Fix `votehub_job`'s `item_count`** so it reflects everything the job stored, not
just the House slice. Without this, VoteHub either gets an expectation that is wrong or
an exemption it does not deserve.

## Open Questions / Risks

- **The expectation values are judgement calls and will be wrong at first.** They should
  live as named constants beside the registry, be easy to tune, and be documented as
  estimates — the same treatment `STALE_THRESHOLD_DAYS` got in #11.
- **False positives are the main risk.** A panel that shows permanent yellow gets
  ignored, which recreates the problem this ticket exists to solve. Prefer starting
  generous and tightening.
- **Retrofitting `last_nonempty_at`.** The column starts NULL for all 17 sources. A NULL
  must not immediately classify everything as `quiet` on deploy — treat NULL as "not yet
  known" and let it populate on the next productive run.
- **Migration.** First ticket in a while that needs one. Additive nullable column, so
  the Alembic autogenerate check T1 added should confirm it cleanly.
- **Does this belong to `shared/` after the extraction?** `SourceRun` is one of the
  cross-cutting pieces T6 has to place. This ticket does not decide that; it just should
  not make the decision harder.
- **Would it actually have caught the two incidents?** Worth checking explicitly against
  the real timeline rather than assuming — that is AC-9.

## References

- `docs/features/ingestion-health/` — PR #9, `SourceRun` and `SOURCE_CADENCE`
- `docs/features/status-admin-consolidation/` — PR #12, exported `classify()`
- `docs/features/economist-discovery-fix/` — #10, the 46-day silent failure
- `docs/features/kalshi-fetch-failure/` — #15, the swallowed-failure version
- `docs/ROADMAP.md` item #13
