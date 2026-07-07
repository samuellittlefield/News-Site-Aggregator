# Acceptance Criteria: District Poll Scraper Fix + VoteHub District Backbone

**Slug:** `district-poll-scraper-fix` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: District polls are fetched from the correct Wikipedia location
- **Given** a competitive district in `COMPETITIVE_DISTRICTS` (e.g. PA-8)
- **When** `fetch_district_polls(db)` runs
- **Then** the service fetches the state-level page (`2026 United States House of
  Representatives elections in <State>`), not a nonexistent per-district page, and locates
  that district's `Polling` subsection within it

### AC-2: Polling subsection is located by structure, not guessed
- **Given** a state's section list (via `action=parse&prop=sections`)
- **When** the service looks for a given district's polls
- **Then** it walks the section tree to find `District {n}` → `General election` →
  `Polling` and fetches that subsection's wikitext by section index — not the whole page

### AC-2b: General-election Polling is never confused with primary Polling
- **Given** a district (e.g. NY-17) whose `Democratic primary` or `Republican primary`
  subsection has its own `Polling` child — real, common case: primary horse-race polling
  between same-party candidates, which appears *earlier in the document* than `General
  election`
- **When** the service resolves the district's polling section
- **Then** it only matches a `Polling` heading that is a descendant of `General election`
  (positioned after that heading, before the next toclevel-1 boundary) — a primary-only
  `Polling` section with no general-election counterpart must resolve to "not found" (AC-7),
  never be mistaken for general-election data

### AC-3: Candidate-named poll tables are parsed correctly
- **Given** a `Polling` subsection whose table headers are candidate names with party in
  parens (e.g. `Rob Bresnahan (R)`, `Paige Cognetti (D)`) rather than generic "Democrat" /
  "Republican" labels
- **When** the service extracts poll rows from that table
- **Then** it correctly maps each candidate column to a party via the `(R)`/`(D)` suffix and
  stores the right dem/rep percentages, pollster name, and dates on the `HousePoll` row

### AC-4: Failures are logged, never silent
- **Given** a state page fetch returns a Wikipedia `error` body (e.g. `missingtitle`), a
  non-200 status, or a district with no resolvable `Polling` section
- **When** that failure occurs
- **Then** it is logged at `warning` level with the state/district and reason — the job
  never silently records "0 new polls" for a real failure the way it does today

### AC-5: One state's failure doesn't starve the others
- **Given** one state's page fetch or parse throws (network error, unexpected structure)
- **When** `fetch_district_polls(db)` processes all states
- **Then** every other state's districts are still fetched and any valid polls from them are
  still stored — matching the existing per-source isolation principle

### AC-6: Re-running the job is idempotent
- **Given** the same district poll already exists in `HousePoll` (same `poll_id`)
- **When** the job runs again with the same upstream data
- **Then** no duplicate row is created; when upstream adds a new poll for that district, only
  the new poll is added

### AC-7: Districts without polling yet are skipped cleanly
- **Given** a competitive district whose race has no `Polling` subsection yet (e.g. still in
  primary, or too low-profile to be polled)
- **When** the service processes that district
- **Then** it's skipped without error or warning — this is an expected, common case, distinct
  from AC-4's real failures

### AC-8: VoteHub district polls are fetched
- **Given** VoteHub's API has polls with `poll_type: "us-representative"` and a `seat_name`
- **When** `fetch_votehub_polls(db)` runs
- **Then** it requests `poll_type=us-representative` (in addition to the existing `approval`
  and `generic-ballot` queries) and parses `seat_name` (e.g. `"AK-01"`) into state + district

### AC-9: Candidate names are mapped to party via the Candidate table, never guessed
- **Given** a VoteHub `us-representative` poll's `answers` list (candidate full names, e.g.
  `"Nick Begich III"`, `"Matt Schultz"`)
- **When** the service resolves each candidate's party
- **Then** it matches the name against `Candidate` rows (`office="H"`, matching state/district)
  and uses that `party`; if a name doesn't match any candidate for that district, or matches
  more than one ambiguously, the poll is skipped and logged — never assigned a guessed party

### AC-10: VoteHub-sourced and Wikipedia-sourced polls are distinguishable
- **Given** both `house_polls.py` (Wikipedia) and `votehub.py` (VoteHub) write into `HousePoll`
- **When** a poll is stored
- **Then** its `source` column is set (`"wikipedia"` or `"votehub"`) and its `poll_id` is
  namespaced accordingly (`wiki-...` / `votehub-...`), so the two streams never collide on the
  same key and can be queried/displayed separately if needed

### AC-11: The VoteHub `partisan` field is never used as candidate party
- **Given** a VoteHub poll has a `partisan` field describing the poll sponsor's lean (e.g.
  `partisan: "DEM"` on a poll sponsored by a Democratic-aligned funder), not the candidate's
  party
- **When** party is assigned to a `HousePoll` row from a VoteHub poll
- **Then** it comes only from the `Candidate` table crosswalk (AC-9) — `partisan` is never read
  as a substitute, even when a candidate name fails to match

## Data Quality / Edge Cases

- **Primary vs. general Polling collision** (see AC-2b): confirmed live in NY-17 and NE-2 —
  both have a `Polling` subsection under a primary section and none yet under `General
  election`. Must resolve as "no general-election polling yet" (AC-7), not misattribute the
  primary numbers.
- **Malformed/missing table**: a `Polling` subsection exists but contains no wikitable, or one
  with unparseable rows (e.g. a prose paragraph instead of a table) → 0 polls extracted for
  that district, no exception, no false-positive rows.
- **Variable table shape**: some polling tables include 3 candidates (major-party + a notable
  independent) or an "Undecided" column, some don't → extraction must key off header content
  (`(R)`/`(D)`/`(I)` suffix), not fixed column position or count.
- **First run vs. re-run**: first run inserts all currently-available polls; re-run with
  unchanged upstream data inserts zero new rows (AC-6).
- **Rate limits / auth**: Wikipedia's `action=parse` API is unauthenticated and has no
  documented rate limit for this volume (~30-40 states with competitive districts, one
  sections call each), consistent with the existing per-district approach's request volume —
  actually fewer requests than today per state with multiple competitive districts.
- **VoteHub name-matching ambiguity**: a district with two same-party primary also-rans still
  in the `Candidate` table (e.g. a losing primary challenger not cleaned up) could make a name
  match ambiguous even when the general-election matchup itself is clear — AC-9 requires
  skip+log here rather than guessing, even though it means fewer polls stored than ideal.
- **Thin VoteHub coverage**: many districts, including some in `COMPETITIVE_DISTRICTS`, will
  simply have zero VoteHub `us-representative` polls — this is a normal empty case, not a
  failure, same spirit as AC-7.

## Out of Scope

- Expanding or refreshing `COMPETITIVE_DISTRICTS` itself (per feature plan's Non-Goals) — this
  fix only affects how polls are fetched for districts already in that list (Wikipedia side;
  VoteHub side isn't gated by this list at all, see feature plan Non-Goals).
- `SourceRun`/ingestion-health tracking (roadmap item #4) — related but separate; not built
  here, though AC-4's logging is a step toward making that feature useful later.
- Any change to `fetch_generic_ballot()` — untouched, works differently, not broken.
- Cross-source reconciliation/conflict surfacing between Wikipedia and VoteHub numbers for the
  same district — both are stored distinguishably (AC-10); comparing/flagging disagreements is
  a follow-up, not required here.
- Fuzzy/nickname-aware candidate name matching — normalization (case, punctuation, common
  suffixes) only; anything beyond that is a skip+log case (AC-9), not a follow-up feature to
  build now.

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
