# Feature Plan: District Poll Scraper Fix + VoteHub District Backbone

**Slug:** `district-poll-scraper-fix` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-07 (v2: added VoteHub scope 2026-07-07)

## Problem / Goal

`house_polls.py`'s `fetch_district_polls()` has never actually ingested a district-level
poll. It's a bug, not a missing feature — confirmed by fetching Wikipedia live:

- `_wiki_page_for_district()` builds page titles like `2026 United States House of
  Representatives election in Pennsylvania's 8th congressional district`. That page format
  doesn't exist for the 2026 cycle — Wikipedia never spun up standalone per-district
  articles. Confirmed via the Wikipedia API and search: every one of the ~55 competitive
  districts in `COMPETITIVE_DISTRICTS` resolves to a 404-equivalent (`missingtitle`).
- The Wikipedia API returns that error as **HTTP 200** with an `{"error": ...}` body — not
  a non-200 status. The existing `if resp.status_code != 200: continue` check never fires,
  so `wikitext` silently becomes `""` and the function returns 0 polls with no error logged.
  This is why the gap has been invisible: it fails clean, every time, for every district.
- Real 2026 district polling exists, but lives nested inside the **state-level** page
  (e.g. `2026 United States House of Representatives elections in Pennsylvania`), under a
  `District 8 → General election → Polling` subsection. Confirmed live for PA-8: 3 real
  polls from June 2026 (post-primary), sitting in a wikitable the app has never reached.
- Even if the scraper pointed at the right section, `_extract_polls_from_wikitext()`
  matches columns by header substring (`"democrat"`/`"dem"`, `"republican"`/`"rep"`). Real
  headers are candidate names with party in parens — `Rob Bresnahan (R)`, `Paige Cognetti
  (D)` — which match neither substring. This would still silently extract 0 rows.

Samuel noticed the symptom now because primaries just finished and general-election polling
volume is ramping up (visible on Wikipedia, invisible in the app) — but the root cause
predates the primaries; it's been broken since this scraper was written.

**v2 addition — Wikipedia isn't the most reliable source available, and a better one is
already integrated and idle.** Checked VoteHub's API (`api.votehub.com/polls`, already
integrated in `votehub.py`, hourly cadence, currently only queried for `approval` and
`generic-ballot`). It has a `poll_type: "us-representative"` category the existing code never
requests. Confirmed live: 51 polls across ~19 districts, structured JSON, a clean `seat_name`
field (`"AK-01"`, `"ME-02"`, `"PA-10"`), pollster, sample size, dates, source URL — no
page-existence guessing, no wikitext scraping, no section-tree fragility. Coverage is much
thinner than Wikipedia's (potentially), but the pipeline is structurally solid where
Wikipedia's is inherently brittle (volunteer-edited, schema-free, prone to exactly the kind of
structural surprises found above). Adding it gives a second, more reliable stream and a
cross-check against the Wikipedia scrape, rather than betting district polling entirely on one
fragile source.

## Context

- **Politics & Polling** domain, per `SOURCES.md` — "House district polls" row
  (`house_polls.py`, 6h cadence, `/api/polls/house*`, Polls tab district map/carousel) and
  "VoteHub polls" row (`votehub.py`, hourly, `/api/votehub/*`).
- Builds on the existing `house_polls.py` service, `votehub.py` service, and `HousePoll` model.
  v1 (Wikipedia fix) is a bug fix to existing logic. v2 (VoteHub) extends an already-integrated
  source to a poll type it doesn't currently query — no new upstream dependency, no new auth.
- Why now: Samuel asked Cowork to check whether the missing new district polling was a bug or
  unbuilt functionality (verified: bug), then asked whether Wikipedia is the most reliable
  source and whether it's worth investigating alternatives now (verified: no, and yes).

## Scope

What's in, v1 (Wikipedia fix) + v2 (VoteHub backbone):

- [x] Changed backend service (`backend/app/services/house_polls.py`) — page-resolution and
  table-extraction logic (v1)
- [x] Changed backend service (`backend/app/services/votehub.py`) — add `us-representative`
  to `POLL_QUERIES`, add a candidate-name→party crosswalk, upsert into `HousePoll` (v2)
- [ ] No new upstream: v1 keeps Wikipedia; v2 extends VoteHub's already-integrated API to a
  poll type it doesn't currently request — neither is a brand-new external dependency
- [ ] No new API route (both write into the existing `HousePoll` table, read via existing
  `/api/polls/house*`)
- [ ] No new scheduler job (v1: same 6h `house_polls_job`; v2: rides the existing hourly
  `votehub_job`)
- [x] Small data model change: add a `source` column to `HousePoll` (`"wikipedia"` |
  `"votehub"`) so the two streams are distinguishable — see `03-implementation-plan.md`
- [ ] No frontend change (existing Polls tab surfaces just start getting real, and now
  multi-sourced, data)

Concretely:

**v1 — Wikipedia fix.** Replaces `_wiki_page_for_district()` + `_extract_polls_from_wikitext()`
with:
1. Fetch the state-level page (`2026 United States House of Representatives elections in
   <State>`) once per state instead of once per district (fewer requests too — e.g. 17
   fetches for PA's 17 districts collapses to 1).
2. Use `action=parse&prop=sections` to find each competitive district's `District N` section
   index, then its nested `General election → Polling` subsection index (see AC-2b — must not
   be confused with a primary section's own `Polling` child).
3. Fetch that subsection's wikitext directly by section index.
4. Parse the poll table by matching `(R)`/`(D)`/`(I)` suffixes in header cells instead of
   generic "democrat"/"republican" substring matching.
5. Surface real fetch failures (non-200, missing section, `error` key in response body) as
   logged warnings instead of silently returning 0.

**v2 — VoteHub backbone.** Extends `votehub.py`:
1. Add `"us-representative": {"poll_type": "us-representative"}` to `POLL_QUERIES`.
2. For each poll with a `seat_name` (e.g. `"AK-01"`), parse state + district from it.
3. Match each `answers[].choice` (candidate full name) against the `Candidate` table
   (`office="H"`, matching state/district) to resolve party — **not** the VoteHub `partisan`
   field, which describes the poll's sponsor lean, not the candidate's party (a trap
   structurally similar to the Wikipedia primary/general Polling mixup in v1 — see AC-11).
4. On an unambiguous single-candidate-per-party match, upsert into `HousePoll` with
   `source="votehub"`, `poll_id="votehub-<votehub id>"`. On an ambiguous or unmatched name,
   skip and log — never guess (AC-9).

## Non-Goals

- Not adding per-district polls for districts outside the existing `COMPETITIVE_DISTRICTS`
  hardcoded list (that list's staleness — e.g. whether it reflects current Cook ratings
  post-primary — is a separate question, worth its own roadmap item if Samuel wants it). Note:
  VoteHub's `us-representative` coverage already includes a few districts outside that list
  (e.g. `PA-10`, `TX-23`, `MT-01`) — v2 stores polls for any district VoteHub covers, it
  doesn't require the district to be in `COMPETITIVE_DISTRICTS` first, since VoteHub gives us
  the seat name directly rather than requiring a pre-seeded district list to scan.
- Not building the "ingestion health tracking" (`SourceRun` table, roadmap item #4) that
  would have caught this automatically — related, but bigger, and already tracked separately.
- Not touching the generic-ballot scraper (`fetch_generic_ballot()`) — that one already reads
  section 9 of the national page directly and works differently; out of scope here.
- Not building cross-source reconciliation/conflict UI (e.g. flagging when Wikipedia and
  VoteHub disagree on a district's numbers) — v1 stores both streams distinguishably via
  `source`; surfacing disagreements is a reasonable follow-up once both streams have run for a
  while, not a v1 requirement.
- Not building fuzzy/nickname-aware candidate name matching beyond straightforward
  normalization (case, punctuation, suffixes like Jr./III) — see Open Questions.

## Proposed Approach

Keep the `async def fetch_*(db)` → upsert → existing router/scheduler pattern (no changes
there). Inside `house_polls.py`:

- Group `COMPETITIVE_DISTRICTS` by state, one `action=parse&prop=sections` call per state
  (not per district) to get the section map.
- For each district in that state, locate `District {n}` in the section list, then walk
  forward through its subsections for `General election` → `Polling`. If no `Polling`
  subsection exists yet (race not polled), skip cleanly — this is a normal/expected case for
  many of the ~55 districts, not an error.
- Fetch wikitext for that specific section index (`section=<idx>`) rather than the whole
  page — keeps payloads small like the current per-district approach did.
- Rewrite `_extract_polls_from_wikitext` (or a new `_extract_polls_from_section`) to key off
  header cells ending in `(R)`/`(D)` rather than substring-matching "democrat"/"republican" —
  this matches what's actually in the wikitext (confirmed against PA-8 live).
- Log a warning (not silent `continue`) whenever a state-level page fetch fails or a
  Wikipedia response contains an `error` key, so this class of bug surfaces in logs going
  forward — ties into (but doesn't require) the ingestion-health roadmap item.

## Open Questions / Risks

- **Spot-check finding (2026-07-07):** the "one Polling subsection per district" assumption
  doesn't hold everywhere. Checked two more states beyond PA-8:
  - **NY-17** (toss-up): has a `Polling` subsection, but it's nested under **Democratic
    primary**, not General election — that's primary horse-race polling (candidate vs.
    candidate), not dem-vs-rep general polling. Its actual `General election` section
    currently has no `Polling` child at all. It also appears *earlier in the document* than
    `General election`, so a naive "find the first Polling heading after District N" approach
    would silently grab the wrong table and mislabel primary numbers as general-election ones.
  - **NE-2** (Lean R, lower-profile): `Democratic primary` also has its own `Polling`
    subsection; `General election` has none yet. Correctly a skip case (AC-7), but same
    primary-vs-general ambiguity risk if section discovery isn't scoped correctly.
  - **Implication:** section discovery must specifically require `Polling` to be a descendant
    of `General election` (i.e., positioned after the `General election` heading and before
    the next toclevel-1 boundary), not just the nearest `Polling` heading anywhere under the
    district. This is now reflected in AC-2 and the implementation plan.
- Wikipedia section numbering shifts as pages are edited — indexing by section title lookup
  (not a hardcoded number) is required, and should be re-resolved on every run rather than
  cached, since state pages are edited frequently during election season.
- Column order/count varies by district (some tables have 3 candidates, some have an
  "Undecided" column, some don't) — extraction needs to key off header content, not fixed
  column positions.
- One state's page structure failing to parse must not block other states — same
  "isolation" principle already in place per-district; needs to hold per-state now that the
  fetch granularity changes.
- Doesn't affect the "one bad source can't starve the rest" pattern at the job level — this
  is entirely inside `refresh_house_polls()`'s existing try/except-per-item shape, just
  applied per-state instead of per-district.
- **v2 (VoteHub) risks:**
  - Candidate name matching is the main open risk. VoteHub gives full display names (`"Nick
    Begich III"`); FEC candidate names may differ in formatting (middle names, nicknames,
    suffix placement). Plan is straightforward normalization + exact match first; ambiguous or
    zero matches are skipped and logged (AC-9), not fuzzy-guessed — wrong-candidate attribution
    is worse than a missing poll.
  - The `partisan` field on a VoteHub poll is the *poll's sponsor's* lean, not the candidate's
    party — confirmed from a real example (an AK-01 poll sponsored by "Bill Hill" tagged
    `partisan: "DEM"`, which is about who commissioned the poll, not who Nick Begich III is).
    Must not be used as a shortcut for party (AC-11).
  - Coverage is thin (51 polls / ~19 districts total, all-time, as of 2026-07-07) — this
    supplements Wikipedia, it doesn't replace it. Framing this as a second stream, not a
    migration, avoids over-promising coverage.
  - VoteHub's `us-representative` polls aren't restricted to `COMPETITIVE_DISTRICTS` — the
    ingestion loop for v2 should iterate over whatever `seat_name`s VoteHub returns, not the
    hardcoded list (see Non-Goals).

## References

- Live verification: `2026_United_States_House_of_Representatives_elections_in_Pennsylvania`,
  section 141 (`District 8 → General election → Polling`) — 3 real June 2026 polls (Lake
  Research Partners, Impact Research, Public Policy Polling), none in the app today.
- Current (broken) code: `backend/app/services/house_polls.py`, `_wiki_page_for_district()`
  (line ~315) and `_extract_polls_from_wikitext()` (line ~336).
- `SOURCES.md` — "House district polls" and "VoteHub polls" rows, Politics & Polling section.
- VoteHub live verification: `GET https://api.votehub.com/polls?poll_type=us-representative`
  (2026-07-07) — 51 polls, e.g. `{"seat_name": "AK-01", "pollster": "Public Policy Polling",
  "answers": [{"choice": "Nick Begich III", "pct": 46.0}, {"choice": "Matt Schultz", "pct":
  39.0}], "partisan": "DEM", ...}`.
- `backend/app/models.py` — existing `Candidate` model (`office`, `state`, `district`, `party`,
  `name`) is the crosswalk source for v2; already populated by `fec_candidates.py`.
