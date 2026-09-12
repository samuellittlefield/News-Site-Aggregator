# Acceptance Criteria: District poll coverage driven by Wikipedia, not a hardcoded list

**Slug:** `district-coverage-from-wikipedia` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: The scrape list comes from Wikipedia, not from the database
- **Given** a `CompetitiveDistrict` table containing an arbitrary set of rows (including
  empty, and including rows for districts that have no polling)
- **When** `fetch_district_polls(db)` runs
- **Then** the set of districts it attempts to scrape is determined entirely by what the
  state pages' section trees contain, and is unaffected by the contents of
  `CompetitiveDistrict` — the service no longer queries that table to build its work list

### AC-2: Every district on a state page is enumerated in one pass
- **Given** a state page whose section tree contains several `District N` headings, some
  with a `General election → Polling` descendant and some without
- **When** the service processes that state
- **Then** it fetches the section list once and yields exactly those district numbers whose
  `District N` block contains a `General election → Polling` descendant — it does not fetch
  the section list once per district, and it does not skip a district merely because that
  district is absent from `CompetitiveDistrict`

### AC-3: The primary-vs-general guard is preserved exactly
- **Given** a district (e.g. NY-17) whose primary subsection has its own `Polling` child
  appearing earlier in the document than `General election`
- **When** the enumeration in AC-2 runs
- **Then** that district is only yielded if a `Polling` heading exists as a descendant of
  `General election`; a primary-only `Polling` section must never cause the district to be
  yielded or its wikitext to be fetched — AC-2b of `district-poll-scraper-fix` continues to
  hold under enumeration, not just under single-district lookup

### AC-4: At-large state pages resolve to the correct title
- **Given** one of the six single-district states (AK, DE, ND, SD, VT, WY)
- **When** the service builds that state's page title
- **Then** it uses the singular form
  (`2026_United_States_House_of_Representatives_election_in_<State>`), the request returns
  200 rather than a `missingtitle` error, and no `missingtitle` warning is logged for these
  six states on a normal run

### AC-5: At-large pages are scraped despite having no `District N` heading
- **Given** an at-large state page whose tree has `General election` at toclevel 1 with a
  `Polling` child, and no `District N` heading anywhere (verified shape for AK on 2026-09-12)
- **When** the service processes that state
- **Then** it resolves the top-level `General election → Polling` section, extracts its poll
  rows, and stores them with `district = 0` — matching the at-large convention already used
  by `_cand_district` in `polls.py:30-32` and by FEC's `district_number`
- **And** an at-large page's *primary* `Polling` section is still never matched (AC-3 applies
  here too — Alaska has both)

### AC-6: `CompetitiveDistrict` keeps its other jobs
- **Given** this change is deployed
- **When** `GET /api/polls/house/districts` is called and when `seed_districts(db)` runs
- **Then** Cook ratings still come from `CompetitiveDistrict` (`polls.py:144`), district
  centroids are unchanged, and `seed_districts()` still upserts the same 60 rows with the
  same values — the table's content and every other consumer are untouched

### AC-7: A district with no polling is a clean skip
- **Given** a `District N` heading with no `General election → Polling` descendant
- **When** the service processes that state
- **Then** the district is simply not scraped: no wikitext request is made for it, no
  warning is logged, and the run is not considered degraded — this is the normal case for
  roughly 349 of 435 districts

### AC-8: One state's failure never starves the others
- **Given** one state page that 404s, returns malformed JSON, or whose section tree raises
  during enumeration
- **When** `fetch_district_polls(db)` runs
- **Then** that state is logged at `warning` level with the state and reason, and the
  remaining 49 states are still processed and their polls still committed — the existing
  per-state `try/except` isolation (AC-5 of `district-poll-scraper-fix`) is preserved

### AC-9: Zero coverage across every state is a failure, not a clean run
- **Given** an upstream change that causes zero districts to resolve a
  `General election → Polling` section across all 50 state pages
- **When** `refresh_house_polls` runs
- **Then** the service raises rather than returning normally, so the scheduler wrapper
  records a `SourceRun` **failure** with the upstream reason for `house_polls_job` — it must
  not record `status: success` with `item_count: 0`, which is the failure mode that hid the
  46-day Economist outage (#10) and the Kalshi incident (#15)

### AC-10: A partial run is still a success
- **Given** some states resolve polling sections and others fail or resolve none
- **When** `refresh_house_polls` runs
- **Then** it commits what it got and returns normally, recording `SourceRun` **success** —
  AC-9 fires only on total zero, so a single bad state page does not take the job down

### AC-11: Re-runs are idempotent and existing rows keep their identity
- **Given** a database already holding Wikipedia-sourced `HousePoll` rows from before this
  change
- **When** `fetch_district_polls(db)` runs twice in a row
- **Then** the first run inserts only genuinely new polls and the second inserts nothing;
  no existing row is duplicated; and the `poll_id` hash
  (`wiki-{state}-{district}-{md5}`) for a poll that was already stored is unchanged, so
  previously-scraped districts do not re-insert under new ids

### AC-12: No contract change anywhere else
- **Given** this change is deployed
- **When** `GET /api/polls/house` and `GET /api/polls/house/districts` are called
- **Then** the response shapes are byte-identical in structure to before (more rows, same
  fields), no Alembic migration exists for this ticket, `house_polls_job` keeps its id and
  6h cadence so `SOURCE_CADENCE` is unchanged, and no frontend file is modified

## Data Quality / Edge Cases

- **Upstream unavailable / malformed:** covered by AC-8 (per-state isolation) and AC-9
  (total-zero raises). A malformed section tree for one state must not raise out of the
  per-state handler.
- **Wikipedia heading-vocabulary drift:** coverage now depends on `District N`,
  `General election` and `Polling` across 50 independently-edited pages. AC-9 is the guard
  that makes a vocabulary change visible instead of silent.
- **First run vs. re-run:** AC-11. Note the Wikipedia path is insert-only by design — it
  never updates an existing row — so a poll whose Wikipedia row is later corrected upstream
  will produce a *new* `poll_id` rather than updating the old one. That is pre-existing
  behaviour, unchanged here, and is roadmap #12's territory.
- **New districts appearing mid-cycle:** the expected steady state. A district that gains a
  polling section between runs is picked up on the next 6h tick with no code or data change.
- **Rate limits:** the Wikipedia API is unauthenticated and the request count does not
  increase (50 section-list calls as before; wikitext calls go from ~31 useful of 60
  attempted to ~86 useful of 86 attempted). No auth or rate-limit behaviour to verify.

## Out of Scope

Restated from the feature plan so none of this gets tested or implemented here:

- Data quality of stored rows — future-dated `end_date`, markup in the pollster field,
  `SurveyUSA`/`Survey USA` dedup, and the null `start_date`/`source_url`/`sample_size`
  columns. All roadmap #12 (`district-poll-data-quality`).
- The VoteHub crosswalk — roadmap #18 (`votehub-candidate-crosswalk-fix`).
- Removing, repurposing, or refreshing `CompetitiveDistrict` or its Cook ratings.
- Changing `item_count` semantics to count upserts rather than inserts.
- Scraping a live ratings source.
- Any frontend change to `DistrictMap` or `PollCarousel`, including how a newly-covered
  safe seat with one lopsided poll is displayed.

## Sign-off
- [x] Samuel has reviewed and approved these criteria — approved 2026-09-12 in Cowork.
- **Stage 4 delegated:** `04-test-cases.md` is to be written by Claude Code as the first
  step of implementation, from these criteria. The criteria above are the source of truth;
  if a case cannot be written against one, stop and raise it rather than reinterpreting it.
