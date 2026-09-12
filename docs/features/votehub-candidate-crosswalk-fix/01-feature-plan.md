# Feature Plan: VoteHub district-poll candidate crosswalk fix

**Slug:** `votehub-candidate-crosswalk-fix` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-09-12

## Problem / Goal

`fetch_votehub_house_polls` resolves each `us-representative` poll's candidates to a party
by matching answer-choice names against the `Candidate` table — never against VoteHub's own
`partisan` field, which is the sponsor's lean (AC-11 of `district-poll-scraper-fix`). Polls
whose candidates cannot be resolved unambiguously are skipped and logged (AC-9). Both
decisions are correct and stay.

The matcher is too brittle to reach those decisions. Measured against the live VoteHub feed
and live FEC data on 2026-09-12:

| stage | count |
|---|---|
| `us-representative` polls returned | 92 |
| dropped — `seat_name: null` | 8 |
| parseable seat | 84 |
| **dropped by the crosswalk** | **54** |
| stored | 30, across 17 districts |

A re-implementation of the crosswalk run against live FEC data reproduced the stored count
of 30 exactly, which is why the causes below can be stated with confidence rather than
guessed at.

**Drop causes** (a poll can hit more than one):

| n | cause | example |
|---|---|---|
| 20 | nickname vs legal given name | FEC `Hurd, Jeffrey` vs VoteHub `Jeff Hurd` |
| 16 | FEC carries an extra token | FEC `Miller-Meeks, Mariannette Jane` vs VoteHub `Mariannette Miller-Meeks` |
| 9 | generic party labels as answer choices | VoteHub `"Rep"` / `"Dem"` |
| 7 | no FEC candidates for the district | all AK-01 — at-large key mismatch |
| 4 | diacritics only | FEC `Salazar, Maria Elvira` vs VoteHub `María Elvira Salazar` |
| 4 | name absent from the FEC set | — |

**Root cause:** `_normalize_name` lowercases, strips punctuation, drops suffixes, then
**sorts the tokens and requires exact set equality**. Token-sorting was added so FEC's
`Last, First` ordering would match VoteHub's `First Last`, and it does — but it makes any
extra, missing, or differently-spelled token a hard miss. FEC `name` is a legal name
including middle names (`.title()`-cased in `fec_candidates.py:160`); VoteHub uses ballot
and common names. The two formats disagree far more often than they agree.

The 7 AK-01 drops are a separate mechanism: `_parse_seat` maps `AK-AL` → `0`, but VoteHub
sends `AK-01`, which parses to district `1`, while FEC uses `district_number` `0` for
at-large. The crosswalk comes back empty every time.

**Goal:** recover the ~45 polls that are genuinely resolvable, keep AC-9 and AC-11 intact,
and make the skip rate visible so a future regression does not hide behind a clean
`SourceRun`.

## Context

- **Domain:** Politics & Polling (elections package). Changes only the VoteHub →
  `HousePoll` path; the approval and generic-ballot loop in `fetch_votehub_polls` is
  untouched, as is `compute_average`.
- **Builds on:** `district-poll-scraper-fix` (#6, PR #8) v2, which introduced this
  crosswalk. AC-9 and AC-11 are that ticket's constraints and are preserved here, not
  revisited.
- **Interacts with:** `poll-staleness-labels` (#11) measures freshness by fieldwork date.
  Recovering 45 polls changes what the district surfaces show but not any average #11 pinned
  — `compute_average` reads `VoteHubPoll`, not `HousePoll`.
- **Sibling ticket:** `district-coverage-from-wikipedia` fixes the other, independent
  coverage bug behind the same flat 112 rows. The two share no code.
- **Why now:** bounded work, a 64% loss on a feed that is already thin, and 52 days to the
  election.

## Scope

- [ ] Changed backend service — `backend/app/elections/services/votehub.py`
- [x] No new/changed data source (same `api.votehub.com/polls`, same query)
- [x] No new/changed API route
- [x] No new/changed scheduler job (`votehub_job`, hourly, unchanged)
- [x] No new/changed data model, therefore **no Alembic migration**
- [x] No frontend change

In scope:

1. **A tolerant but still-strict matcher.** Match on surname plus first given name with
   diacritics folded, tolerating extra middle tokens on either side, instead of demanding
   equal token sets. Ambiguity still loses: if a relaxed match resolves to more than one
   candidate of differing parties, the poll is skipped exactly as today.
2. **At-large seat normalization.** `XX-01` for a single-district state resolves to district
   `0`, matching FEC and the existing `polls.py:30-32` convention.
3. **An aggregate skip signal.** Today every skip logs its own WARNING with the unmatched
   names — the evidence was in the logs all along, but nothing counts it, so a 64% drop
   rate reads as a healthy run. Emit a per-run summary (returned/parsed/stored/skipped by
   cause) so the rate is observable.

## Non-Goals

- **Not** using VoteHub's `partisan` field. AC-11 stands.
- **Not** guessing on ambiguity. AC-9 stands — a relaxed matcher must not become a
  permissive one, and this plan trades zero-match failures for coverage, never
  ambiguous-match failures for coverage.
- **Not** fixing the 8 `seat_name: null` polls. Unparseable upstream; nothing to match on.
- **Not** changing how FEC names are ingested. `fec_candidates.py` keeps storing the FEC
  legal name as-is; the tolerance belongs in the matcher, not in mutating stored data.
- **Not** the Wikipedia stream — sibling ticket.
- **Not** alerting. Consistent with #13's reasoning that zero traffic makes alerting
  heavy-handed today; the summary line and `SourceRun` are the surface.

## Proposed Approach

Keep `_district_candidates` / `_match_candidate_party` as the seam and change what counts as
a match:

1. Build the per-district crosswalk keyed by **(folded surname, folded first given name)**
   rather than a sorted full-token string. Diacritic folding via Unicode NFD with combining
   marks stripped, applied to both sides. FEC's `Last, First Middle` and VoteHub's
   `First Middle Last` both reduce to the same pair, so the 16 extra-token and 4 diacritic
   drops resolve without weakening anything.
2. Fall back to surname-only **only when it is unique within the district**, which is what
   recovers the 20 nickname cases (`Jeff` vs `Jeffrey`) without guessing. Two candidates
   sharing a surname in one district returns `None`, as now.
3. Normalize at-large seats before the crosswalk lookup.
4. Count outcomes per run and log one summary line alongside the existing per-poll warnings.

**Critical implementation detail (AC-2b).** Do not derive VoteHub's surname by taking the
last token. Roughly 11 of the drops have multi-token surnames (`De La Cruz`, `Van Orden`,
`Gluesenkamp Perez`, `Miller-Meeks`, `von Wilpert`) where the last token is only part of the
surname. Match by testing whether the FEC surname's tokens form a contiguous suffix of the
VoteHub name's tokens. A first draft of this design got it wrong and left those 11 unresolved.

**Expected recovery, measured 2026-09-12 by running the proposed matcher against the live
feed and live FEC data: 30 stored today → 67 stored, i.e. +37 polls.** An earlier estimate of
"~45 of 54" in this plan was too optimistic and is superseded; it assumed every non-generic
-label drop would resolve.

The 8 residual skips break down as: 4 same-party or non-D-vs-R generals that `HousePoll`
cannot represent (roadmap #20), and 4 with no stored candidate match — `Nick LaLota` (NY-01),
`Janelle Stetson` (PA-10, where VoteHub misspells FEC's `Stelson`), `Lupe Castillo` (IL-04,
filtered out of our table — roadmap #19), and two minor AK-AL candidates. The 9 generic-label
polls are excluded on purpose (AC-8).

## Open Questions / Risks

1. ~~**The 9 `"Rep"` / `"Dem"` polls — resolve them or leave them?**~~ **DECIDED 2026-09-12:
   left out of v1.** See AC-8. Original reasoning retained below.

   Their answer choices are
   party labels, not candidate names, so no crosswalk can ever match them. Reading the label
   directly is *not* the AC-11 violation it might look like: AC-11 forbids trusting the
   sponsor's `partisan` lean, whereas here the label is the answer itself. But these are
   generic-ballot-shaped questions asked within a district, which is arguably a different
   measurement from a named head-to-head. **Recommend** leaving them out of v1 and deciding
   separately, since mixing them into the same `HousePoll` rows would make the district
   surfaces compare unlike things.
2. **How strict should the surname-only fallback be?** It is what recovers the largest
   bucket (20), and it is also the loosest rule in the plan. Scoping it to "unique surname
   within this district's FEC candidate set" keeps it defensible, but it will occasionally
   match a minor candidate who happens to share a surname with the polled one. Worth an
   explicit AC and a test case with a deliberately colliding pair.
3. **The 4 names absent from FEC entirely.** Some are likely candidates who have not filed
   or raised money, and `fetch_house_candidates` filters on
   `incumbent == "I" or in competitive_keys or has_raised_funds`
   (`fec_candidates.py:217`). Note the coupling: `competitive_keys` comes from
   `CompetitiveDistrict`, so a district outside the 60-row seed list only gets candidates if
   they are incumbents or have raised funds. **This means the sibling ticket's coverage work
   can widen this ticket's crosswalk gaps** — more polled districts whose candidate sets are
   thinner. Flagging as a real cross-ticket interaction; recommend measuring after both ship
   rather than pre-emptively loosening the FEC filter.
4. **Upstream sparsity bounds the win.** VoteHub returns 92 district polls total, newest
   fieldwork 2026-09-03, only 4 in the last 14 days. This ticket recovers rows; it does not
   make the feed fresh.
5. **Idempotency.** The upsert is keyed on `votehub-{id}`, unchanged, so newly-resolvable
   polls insert once and re-runs stay clean. Worth a test case per the project's upsert rule.

## References

- Diagnosis, 2026-09-12 — Project Nebula doc `claude/house-district-polls-diagnosis-2026-09-12.md`
- `docs/features/district-poll-scraper-fix/` — AC-9 (never guess on ambiguity), AC-11
  (never trust `partisan`)
- `backend/app/elections/services/votehub.py` — `_normalize_name`, `_district_candidates`,
  `_match_candidate_party`, `_parse_seat`
- `backend/app/elections/services/fec_candidates.py:160, 217` — FEC name casing and the
  candidate filter
- `backend/app/elections/routers/polls.py:30-32` — at-large `"AL"` → `0` convention
