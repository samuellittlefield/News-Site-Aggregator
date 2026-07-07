# Test Cases: District Poll Scraper Fix + VoteHub District Backbone

**Slug:** `district-poll-scraper-fix` &nbsp; **Source:** `02-acceptance-criteria.md`

> Note: the pipeline template assumes no test harness exists yet. That's stale — `backend/tests/`
> (pytest + respx + a transactional `db` fixture, see `test_kalshi_upsert.py`/`conftest.py`) has
> existed since `test-harness-ci` shipped. All cases below are written as real pytest cases in
> `backend/tests/test_house_polls.py`, following the `test_kalshi_upsert.py` pattern (respx
> mocks upstream, `db` fixture for a rollback-per-test session).

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1, AC-2 | TC-1 |
| AC-2b | TC-7 |
| AC-7 | TC-2 |
| AC-3 | TC-3 |
| AC-4 | TC-4 |
| AC-5 | TC-5 |
| AC-6 | TC-6 |
| AC-8 | TC-8 |
| AC-9 | TC-9 |
| AC-10 | TC-10 |
| AC-11 | TC-11 |

## Backend

### TC-1 — Section discovery resolves the right Polling subsection (covers AC-1, AC-2)
- **Type:** unit (`_fetch_state_sections` + `_find_polling_section`)
- **Setup:** respx-mock `action=parse&prop=sections` for the Pennsylvania state page with a
  fixture (`backend/tests/fixtures/pa_house_sections.json`) built from the real section list
  captured 2026-07-07 (District 8 = index 124, its `Polling` subsection = index 141)
- **Steps:**
  1. Call `_fetch_state_sections(client, "PA")`
  2. Call `_find_polling_section(sections, district=8)`
- **Expected Result:** returns section index `141`; a second district in the same fixture with
  a known different index (e.g. District 7) resolves to its own correct index, not District 8's
- **Automation note:** pytest, respx-mocked, no live network call

### TC-2 — District with no Polling subsection yet is skipped, not errored (covers AC-7)
- **Type:** unit (`_find_polling_section`)
- **Setup:** a sections fixture for a district still mid-primary (no `General election` /
  `Polling` children under its `District N` heading)
- **Steps:**
  1. Call `_find_polling_section(sections, district=<that district>)`
- **Expected Result:** returns `None`; calling code's loop `continue`s without logging a warning
  (distinguish from TC-4's real-failure logging)

### TC-3 — Candidate-named header parsing extracts correct dem/rep values (covers AC-3)
- **Type:** unit (`_extract_polls_from_polling_section`)
- **Setup:** the real PA-8 `Polling` wikitext captured 2026-07-07
  (`backend/tests/fixtures/pa8_polling_section.wikitext` — 3 polls: Lake Research Partners
  47/45, Impact Research 46/45, Public Policy Polling 45/43, headers `Rob Bresnahan (R)` /
  `Paige Cognetti (D)`)
- **Steps:**
  1. Call `_extract_polls_from_polling_section(wikitext, "PA", 8)`
- **Expected Result:** returns 3 poll dicts; each has `dem` and `rep` populated with the correct
  values (not swapped), `pollster` set from the row's first cell (citation/ref markup stripped),
  `state="PA"`, `district=8`
- **Edge case within this TC:** confirm a header ending in `(I)` (independent candidate) is
  captured too (not dropped), even though the AC only requires `dem`/`rep` to be correctly
  attributed — verifies the party-suffix approach generalizes past a strict two-column case

### TC-7 — Primary-only Polling section is never mistaken for general-election polling (covers AC-2b)
- **Type:** unit (`_find_polling_section`)
- **Setup:** a sections fixture built from the real NY-17 section list captured 2026-07-07 —
  `Democratic primary` (toclevel 2) has a `Polling` child (toclevel 3, primary horse-race
  polls), `General election` (toclevel 2, appearing later in the document) has no `Polling`
  child at all
- **Steps:**
  1. Call `_find_polling_section(sections, district=17)`
- **Expected Result:** returns `None` (falls through to AC-7's clean-skip path) — must NOT
  return the primary section's index. This is the regression test for the specific failure
  mode found during the 2026-07-07 spot check: a naive "first Polling heading under the
  district" search would grab the Democratic primary's polling table and mislabel
  candidate-vs-candidate primary numbers as general-election dem/rep numbers
- **Companion case:** repeat with a fixture where `General election` *does* have its own
  `Polling` child positioned after a primary section's own `Polling` child (construct
  synthetically if no live example is found) — confirm the general-election one is returned,
  not the primary one

### TC-4 — Missing-page / non-200 state fetch is logged, not silently swallowed (covers AC-4)
- **Type:** unit (`_fetch_state_sections`)
- **Setup:** respx-mock the sections endpoint returning HTTP 200 with a MediaWiki
  `{"error": {"code": "missingtitle", ...}}` body (this is the exact shape that caused the
  original bug)
- **Steps:**
  1. Call `_fetch_state_sections(client, "ZZ")` (a state with no real page, for test purposes)
  2. Capture logs via `caplog`
- **Expected Result:** returns `[]`; a `warning`-level log line is emitted naming the state and
  the `missingtitle` reason — this is the regression test for the original silent-failure bug

### TC-5 — One state's failure doesn't block other states (covers AC-5)
- **Type:** integration (`fetch_district_polls`)
- **Setup:** respx-mock two states' worth of competitive districts in `COMPETITIVE_DISTRICTS`
  (or a test-local subset) — one state's sections endpoint raises/returns an error, the other
  returns a valid fixture with one pollable district
- **Steps:**
  1. Call `await fetch_district_polls(db)`
- **Expected Result:** the failing state contributes 0 polls and is logged (per TC-4); the
  healthy state's poll(s) are still inserted into `HousePoll`

### TC-6 — Re-run is idempotent; new upstream data adds only the new row (covers AC-6)
- **Type:** integration (`fetch_district_polls`), mirrors `test_kalshi_upsert.py`'s structure
- **Setup:** respx-mock PA-8's sections + polling wikitext with the 3-poll fixture from TC-3
- **Steps:**
  1. Run 1: call `fetch_district_polls(db)` → assert 3 `HousePoll` rows for PA-8
  2. Run 2 (identical fixture): call again → assert still 3 rows, no duplicates
  3. Run 3: mutate the fixture to add a 4th poll → call again → assert 4 rows total, and the
     original 3 are unchanged (same `poll_id`s, same values)
- **Expected Result:** upsert key (`poll_id` hash) prevents duplication; new data is additive

### TC-8 — VoteHub `us-representative` polls are fetched and parsed (covers AC-8)
- **Type:** integration (`fetch_votehub_polls` / new house-polls branch), in
  `backend/tests/test_votehub_house_polls.py`
- **Setup:** respx-mock `GET api.votehub.com/polls?poll_type=us-representative` with a
  trimmed real fixture (`backend/tests/fixtures/votehub_us_representative.json` — the live
  AK-01 example: Nick Begich III 46%, Matt Schultz 39%, `seat_name: "AK-01"`). Seed the test DB
  with matching `Candidate` rows (`office="H"`, `state="AK"`, `district=1`, one `party="REP"`
  named "Nick Begich III", one `party="DEM"` named "Matt Schultz")
- **Steps:**
  1. Call the VoteHub house-polls fetch function
- **Expected Result:** one `HousePoll` row created, `state="AK"`, `district=1`, `source="votehub"`,
  `rep`/`dem` populated matching the correct candidate (not swapped)

### TC-9 — Unmatched or ambiguous candidate name is skipped and logged, not guessed (covers AC-9)
- **Type:** unit (`_match_candidate_party`) + integration
- **Setup:** (a) a VoteHub poll whose candidate name doesn't match any seeded `Candidate` for
  that district; (b) a district seeded with two `Candidate` rows sharing the same normalized
  name (ambiguous match)
- **Steps:**
  1. Call the fetch function with each setup
  2. Capture logs via `caplog`
- **Expected Result:** in both cases, no `HousePoll` row is created for that poll, and a
  `warning`-level log line names the district and the unresolved candidate — confirms AC-9's
  "never guess" requirement holds for both the zero-match and ambiguous-match cases

### TC-10 — VoteHub and Wikipedia rows are distinguishable and don't collide (covers AC-10)
- **Type:** integration
- **Setup:** seed one Wikipedia-sourced `HousePoll` row for PA-8 (from TC-3/TC-6's fixture) and
  run the VoteHub fetch with a fixture that also has a PA-8 poll
- **Steps:**
  1. Run both `fetch_district_polls(db)` (Wikipedia) and the VoteHub house-polls fetch
- **Expected Result:** both rows exist for PA-8, `source="wikipedia"` on one, `source="votehub"`
  on the other, distinct `poll_id`s (`wiki-...` vs `votehub-...`) — no unique-constraint
  collision, no overwrite of one by the other

### TC-11 — `partisan` field is never used as candidate party (covers AC-11)
- **Type:** unit (`_match_candidate_party` / the upsert branch)
- **Setup:** a VoteHub poll fixture where `partisan` is deliberately set to the *opposite* of
  at least one candidate's actual party (e.g. `partisan: "DEM"` on a poll where the Republican
  candidate is the first `answers` entry) — mirrors the real AK-01 example where `partisan`
  reflects the poll's sponsor, not either candidate
- **Steps:**
  1. Run the fetch/match logic against this fixture
- **Expected Result:** stored `dem`/`rep` values match the `Candidate` table's actual party
  assignments, not `partisan` — asserts the field is never read in the party-resolution path
  (grep the implementation for `partisan` usage as an additional static check, since this is a
  "did we accidentally use a convenient-looking wrong field" class of bug)

## Edge Cases & Failure Modes
- Polling subsection exists but its wikitable is malformed/unparseable → 0 polls, no exception
  (covered implicitly by TC-1/TC-3's fixture design; add a dedicated malformed-table fixture if
  Claude Code finds a real-world example worth regression-testing)
- Wikipedia rate limiting / timeout → falls under TC-4's "log, don't silently succeed" pattern
- Table with an `Undecided`-only extra column (no party suffix) → ignored, not misattributed to
  either party (assert explicitly in TC-3)
- VoteHub name variants (middle initials, suffix placement/punctuation differences between
  VoteHub's `answers[].choice` and the `Candidate.name` on file) → covered by TC-9's ambiguous
  case; add real-world variants to the normalization function's unit tests as Claude Code finds
  them during implementation, rather than trying to enumerate every variant up front
- VoteHub poll with only one candidate in `answers` (e.g. an approval-style question mixed into
  the `us-representative` type by mistake upstream) → skip, don't crash; worth an explicit unit
  test if Claude Code finds a real example

## Regression Check
- `/api/polls/house` and `/api/polls/house/*` routes (`backend/app/routers/polls.py`) — confirm
  response shape unchanged (same `HousePollOut` model plus the new `source` field), only row
  *contents* change otherwise
- `fetch_generic_ballot()` — untouched; confirm existing generic-ballot tests (if any) still pass
- `fetch_votehub_polls()`'s existing `approval`/`generic-ballot` behavior — confirm unaffected by
  the new `us-representative` branch (same isolation principle, now within `votehub.py` too)
- Polls tab district map/carousel — manual smoke check that it renders correctly once real,
  multi-sourced rows exist (no component change expected, but first real data is a good time to
  eyeball it)
- `seed_districts()` — untouched; confirm `CompetitiveDistrict` seeding still runs fine
  alongside the new `fetch_district_polls` flow in `refresh_house_polls()`
- Alembic migration for `HousePoll.source` — confirm `alembic upgrade head` applies cleanly
  against a DB with existing (pre-fix) `house_polls` rows, and that `alembic downgrade -1`
  cleanly reverts it

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
