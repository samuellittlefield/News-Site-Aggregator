# Feature Plan: District poll coverage driven by Wikipedia, not a hardcoded list

**Slug:** `district-coverage-from-wikipedia` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-09-12

## Problem / Goal

`/api/polls/house` has been flat at 112 rows across 37 of 435 districts. Diagnosis on
2026-09-12 found no ingestion failure: both jobs run and succeed, and their
`item_count: 0` correctly means "no new `poll_id` seen" (both counters increment only on
insert). The Wikipedia stream is coverage-capped instead.

`fetch_district_polls` (`house_polls.py:654-656`) builds its work list from
`db.query(CompetitiveDistrict).all()`. That table is populated only by `seed_districts()`
from the hardcoded `COMPETITIVE_DISTRICTS` literal — **60 rows, unchanged since commit
`a39fc85` on 2026-06-02**, and `seed_districts()` upserts without ever deleting, so the
table can never hold anything else. The scraper therefore visits 60 districts and no more,
a 13.8% ceiling on a 435-seat chamber.

Measured live against all 50 state pages on 2026-09-12:

| | districts |
|---|---|
| Have a `District N → General election → Polling` section on Wikipedia | **86** |
| The scraper actually visits | 31 |
| **Available but never fetched** | **55** |

Misses include IA-1, IA-2, CO-3, NE-1, PA-10, TX-23, VA-1, NY-21, MI-4, CA-40 — real 2026
battlegrounds. The inverse waste matters too: **29 of the 60 seeded districts have no
polling section at all**, so roughly half the seed list is dead fetches every six hours.

The list is also no longer a defensible competitiveness judgment: FL-10 is labeled
"Likely D" at a +48.2 2024 margin, SC-1 "Likely D" at −6.4.

**Goal:** stop deciding in advance which districts might have polls. Let Wikipedia's own
section tree name them, so coverage grows on its own as the cycle heats up toward
3 November and no one has to maintain a list.

## Context

- **Domain:** Politics & Polling (elections package). Per `SOURCES.md`, the "House district
  polls" row covers two streams into `HousePoll` distinguished by `source`; this ticket
  changes only the **Wikipedia** stream's target selection.
- **Builds on:** `district-poll-scraper-fix` (#6, PR #8), which built the section-tree
  resolution this ticket reuses unchanged — including the AC-2b guard requiring `Polling`
  to be a descendant of `General election` rather than of a primary section.
- **Adjacent, deliberately separate:** roadmap #12 `district-poll-data-quality` owns the
  quality of rows already stored (future-dated rows, markup in the pollster field, dedup
  variants). This ticket owns *how many districts get scraped* and touches none of that.
- **Why now:** 52 days to the election, and the gap is pure coverage loss on a surface
  (district map, carousel) whose whole point is breadth. The fix costs no extra upstream
  requests.

## Scope

v1 changes the Wikipedia stream's district selection and fixes at-large state pages.

- [ ] Changed backend service — `backend/app/elections/services/house_polls.py`
- [x] No new/changed data source (same Wikipedia API, same endpoints)
- [x] No new/changed API route (`/api/polls/house*` response shape unchanged)
- [x] No new/changed scheduler job (`house_polls_job`, 6h, unchanged)
- [x] No new/changed data model, therefore **no Alembic migration**
- [x] No frontend change (`DistrictMap`, `PollCarousel` render whatever rows exist)

In scope:

1. **Derive the scrape list from the section tree.** For each of the 50 state pages, walk
   the already-fetched section list for every `District N` heading that has a
   `General election → Polling` descendant, and scrape exactly those. `CompetitiveDistrict`
   stops being the work list.
2. **At-large states.** Six state pages currently 404 with `missingtitle` on every run:
   AK, DE, ND, SD, VT, WY. Verified 2026-09-12 — they use the **singular** title
   (`2026_United_States_House_of_Representatives_election_in_Alaska`), and four of the six
   (AK, VT, WY, SD) have a general-election `Polling` section today. These pages have no
   `District N` wrapper: `General election` sits at toclevel 1 with `Polling` as its child.
   They store as district `0`, matching the existing at-large convention in
   `polls.py:30-32` (`_cand_district`: `"AL"` → `0`).
3. **Observable degraded path.** A run that resolves zero polling sections across all 50
   states is an upstream change, not a quiet success — it must surface rather than record
   `success` / `item_count: 0`. See Open Questions for the exact threshold.

## Non-Goals

- **Not** fixing data quality of stored rows — roadmap #12 owns that.
- **Not** the VoteHub crosswalk — separate ticket, `votehub-candidate-crosswalk-fix`.
- **Not** removing or repurposing `CompetitiveDistrict`. It keeps serving Cook ratings to
  `/api/polls/house/districts` (`polls.py:144`) and district centroids to the map;
  `seed_districts()` stays as-is. This ticket only stops it doubling as a scrape allowlist.
- **Not** refreshing the Cook ratings data itself. Stale ratings are a separate question,
  and once coverage no longer depends on them the urgency drops.
- **Not** changing `item_count` semantics to count upserts. The counter is behaving
  correctly; the diagnosis mistake was reading `0` as failure. Any freshness signal should
  come from fieldwork dates, per the #11 precedent.
- **Not** scraping a live ratings source (Cook, Sabato). Considered and rejected — a new
  fragile dependency for a judgment this feature no longer needs.

## Proposed Approach

`fetch_district_polls` already fetches one section list per state via
`_fetch_state_sections`. The change is to derive districts from that response instead of
from the database:

1. Replace the `by_state` construction with a per-state walk that yields every district
   number whose `District N` block contains a `General election → Polling` descendant.
   `_find_polling_section` already implements the descendant rule for one known district —
   generalize it to enumerate all of them in one pass, preserving the AC-2b guard exactly.
2. For a page with no `District N` headings, look for a top-level `General election →
   Polling` and yield district `0`.
3. `_state_wiki_page` gains at-large handling: the six single-district states resolve to
   the singular `election` title. Prefer a small explicit set over a fallback retry, so a
   genuine 404 on a multi-district state still logs loudly instead of being masked by a
   second attempt.
4. Everything downstream is untouched: `_fetch_section_wikitext`,
   `_extract_polls_from_polling_section`, the `poll_id` hash, and the insert-only upsert all
   stay as they are, so re-runs remain idempotent and existing rows keep their ids.

Request cost is unchanged in the state-list phase (still 50) and drops in the section
phase: 86 real sections instead of 60 lookups of which 29 resolve to nothing.

## Open Questions / Risks

1. **What is the zero-coverage failure threshold?** Per the skill's degraded-path rule and
   the #10/#15 precedent, a hollow success is the bug pattern this project keeps hitting.
   Zero sections across all 50 states should clearly raise. Less clear: should a single
   state page 404 stay a warning (today's behaviour, AC-4 of #6), or should N-of-50 page
   failures escalate? **Recommend** raising only on total-zero for v1, since the at-large
   fix removes the six known-noisy 404s and leaves any remaining one genuinely notable.
2. **Does removing the ratings filter pull in noise?** Districts outside the seed list
   include safe seats with a single lopsided poll. This is a display question for the
   district map, not an ingestion one, and the map already renders the full 435-district
   `house_priors.csv` universe regardless of poll coverage (`polls.py:131-137`). Flagging
   rather than pre-solving.
3. **Wikipedia section-title drift.** Coverage now depends on the heading vocabulary
   (`District N`, `General election`, `Polling`) across 50 independently-edited pages. This
   dependency already exists from #6; this ticket widens it from 60 districts to all of
   them. The total-zero guard in (1) is what catches a vocabulary change.
4. **Failure isolation.** The existing per-state `try/except` must stay — one state's
   malformed tree cannot abort the other 49. Worth an explicit AC and test case.
5. **No dependency on in-flight work.** `scheduler-split` (T2) is specced but untouched
   here; `house_polls_job` keeps its id and cadence, so `SOURCE_CADENCE` needs no change.

## References

- Diagnosis, 2026-09-12 — Project Nebula doc `claude/house-district-polls-diagnosis-2026-09-12.md`
- `docs/features/district-poll-scraper-fix/` — AC-2b (primary-vs-general guard), AC-4
  (failures logged not silent), AC-5 (per-state isolation)
- `docs/features/economist-discovery-fix/` and `kalshi-fetch-failure/` — prior art for
  "zero results is a failure, not a success"
- `backend/app/elections/routers/polls.py:30-32` — at-large `"AL"` → `0` convention
- `SOURCES.md` — "House district polls" row
