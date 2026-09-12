# Test Cases: District poll coverage driven by Wikipedia, not a hardcoded list

**Slug:** `district-coverage-from-wikipedia` &nbsp; **Source:** `02-acceptance-criteria.md`

> All cases are backend pytest, following `test_house_polls.py`'s existing pattern
> (docstring cites AC/TC IDs, `db`/`respx_router` fixtures, `respx_router` autouse network
> guard per `conftest.py`). No frontend surface changes in this ticket, so there is no
> manual/click-through section. New fixture `ak_house_sections.json` is added per the
> implementation plan; `pa_house_sections.json` and `ny17_house_sections.json` are reused
> unchanged.

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2, TC-3, TC-8, TC-9 |
| AC-3 | TC-4, TC-5 |
| AC-4 | TC-6 |
| AC-5 | TC-6, TC-7 |
| AC-6 | TC-10 |
| AC-7 | TC-11 |
| AC-8 | TC-12 |
| AC-9 | TC-13, TC-14 |
| AC-10 | TC-15 |
| AC-11 | TC-16 |
| AC-12 | TC-17 |
| (regression gate) | TC-0a, TC-0b |

## Regression Gate — run before touching `fetch_district_polls`

### TC-0a — Existing section-resolution test passes unmodified (regression gate for the refactor)
- **Type:** unit, existing test, unmodified
- **Steps:** Run `test_find_polling_section_resolves_correct_index` (`test_house_polls.py`,
  labeled TC-1 in that file) as-is against the rewritten `_find_polling_section`
- **Expected Result:** passes unmodified — `_find_polling_section(sections, 8) == 141` and
  `_find_polling_section(sections, 7) == 111` against `pa_house_sections.json`, proving
  `_find_polling_section` as `dict(_iter_polling_sections(sections)).get(district)` agrees
  with the pre-refactor behaviour
- **Automation note:** this is `03-implementation-plan.md` step 2's gate; do not edit this
  test to make it pass

### TC-0b — Primary-only Polling still excluded after the refactor (regression gate)
- **Type:** unit, existing test, unmodified
- **Steps:** Run `test_primary_only_polling_is_not_returned` (`test_house_polls.py`, labeled
  TC-7 in that file) as-is
- **Expected Result:** passes unmodified — `_find_polling_section(sections, 17)` on
  `ny17_house_sections.json` is still `None`
- **Automation note:** same gate as TC-0a; both must be green before `fetch_district_polls`
  is rewritten

## Backend

### TC-1 — `fetch_district_polls` never queries `CompetitiveDistrict` for its work list (covers AC-1)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** empty `CompetitiveDistrict` table (no `_seed_district` calls); mock all 50
  states' sections responses via `respx_router` side_effect, returning `PA_SECTIONS` for PA
  and empty-sections (`{"parse": {"sections": []}}`) for every other state
- **Steps:**
  1. Call `await house_polls.fetch_district_polls(db)` with `CompetitiveDistrict` empty
  2. Assert `HousePoll` rows for PA district 8 were still inserted
- **Expected Result:** PA-8 polls are scraped and stored even though `CompetitiveDistrict`
  has zero rows for PA — proving the work list comes from Wikipedia's section tree, not the
  database
- **Automation note:** a variant of the existing `test_one_state_failure_does_not_block_others`
  setup with `_seed_district` calls removed entirely

### TC-2 — Enumeration yields every district with general-election Polling, in one sections fetch (covers AC-2)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Steps:**
  1. Call `house_polls._iter_polling_sections(_sections(PA_SECTIONS))`
  2. Collect the result into a dict
- **Expected Result:** the dict contains `{7: 111, 8: 141}` and does **not** contain `9`
  (District 9 has only a primary Polling child, no `General election` section at all — AC-7);
  exactly one call was made to fetch `PA_SECTIONS` (assert via `respx_router` call count if
  the sections fetch is exercised in this test, or assert directly on the in-memory list if
  operating on the fixture without a network round trip)

### TC-3 — Enumeration does not skip a district absent from `CompetitiveDistrict` (covers AC-2)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** `CompetitiveDistrict` table seeded with only PA-7 (PA-8 deliberately absent)
- **Steps:**
  1. Mock PA's sections response with `PA_SECTIONS` and PA-8's wikitext with `PA8_WIKITEXT`
  2. Call `await house_polls.fetch_district_polls(db)`
- **Expected Result:** PA-8 polls are inserted despite PA-8 having no `CompetitiveDistrict`
  row — enumeration is driven by the section tree, not by which districts were seeded

### TC-4 — Primary-only Polling is excluded under enumeration, not just single-district lookup (covers AC-3)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Steps:**
  1. Call `house_polls._iter_polling_sections(_sections(NY17_SECTIONS))`
- **Expected Result:** the result does not contain district `17` — NY-17 has a primary
  `Polling` child but no `General election → Polling` descendant; this is the enumerator
  form of TC-0b and the case the implementation plan flags as most likely to regress

### TC-5 — General Polling after a primary Polling is still yielded correctly under enumeration (covers AC-3)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Steps:**
  1. Build the six-section fixture already used inline in
     `test_general_polling_after_primary_polling_is_returned` (District 5: primary Polling at
     index 12, general Polling at index 22)
  2. Call `house_polls._iter_polling_sections(sections)`
- **Expected Result:** the result contains `{5: 22}` — the general-election Polling index,
  never the primary's 12

### TC-6 — At-large state page title uses the singular form and returns 200 (covers AC-4)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Steps:**
  1. For each state in `house_polls.AT_LARGE_STATES` (`AK`, `DE`, `ND`, `SD`, `VT`, `WY`),
     assert `house_polls._state_wiki_page(state)` equals
     `f"2026_United_States_House_of_Representatives_election_in_{STATE_NAMES[state]}"`
     (singular `election`)
  2. For a non-at-large state (e.g. `PA`), assert the existing plural form
     (`..._elections_in_Pennsylvania`) is unchanged
  3. Mock the singular-titled URL to return 200 with `ak_house_sections.json` and call
     `await house_polls._fetch_state_sections(client, "AK")` directly
- **Expected Result:** the six at-large states resolve to the singular title string; the
  mocked 200 response is consumed without a `missingtitle` warning logged (assert via
  `caplog`); non-at-large states are unaffected

### TC-7 — At-large enumeration yields district 0 from a top-level Polling section, ignoring the primary (covers AC-5)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** new fixture `ak_house_sections.json` per the implementation plan — `General
  election` at toclevel 1 with `Polling` at index 26, plus a `Primary election` section with
  its own `Polling` at index 19, and no `District N` heading anywhere
- **Steps:**
  1. Call `house_polls._iter_polling_sections(_sections(AK_SECTIONS))`
- **Expected Result:** the result is exactly `{0: 26}` — district 0 maps to the general
  Polling index; index 19 (the primary's Polling) never appears as a value in the result —
  this single fixture covers AC-4 (via TC-6), AC-5, and AC-3-on-an-at-large-page together,
  per the implementation plan's fixture note

### TC-8 — Section-list fetch happens once per state, not once per district (covers AC-2, AC-5)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** `PA_SECTIONS` mocked for PA's `prop=sections` call; PA has two districts with
  resolvable Polling (7 and 8)
- **Steps:**
  1. Call `await house_polls.fetch_district_polls(db)` with only PA reachable
  2. Assert the number of `respx_router` calls with `prop=sections` for the PA page equals 1
- **Expected Result:** exactly one sections request for PA even though two districts (7 and
  8) are enumerated from it — confirms the rewritten loop still fetches the section list once
  per state (this was already true before the refactor; the case guards against a regression
  where per-district enumeration accidentally re-fetches sections)

### TC-9 — All 50 states are attempted regardless of `CompetitiveDistrict` contents (covers AC-2, AC-5)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** `CompetitiveDistrict` empty; mock every state in `STATE_NAMES` to return
  empty sections except PA (`PA_SECTIONS`)
- **Steps:**
  1. Call `await house_polls.fetch_district_polls(db)`
  2. Assert the sections endpoint was called once for each of the 50 keys in
     `house_polls.STATE_NAMES`
- **Expected Result:** every state is attempted — the iteration source is `STATE_NAMES`
  (all 50), not a derived set from `CompetitiveDistrict`

### TC-10 — `CompetitiveDistrict`'s other consumers are unaffected (covers AC-6)
- **Type:** unit + integration, `backend/tests/test_house_polls.py` and
  `backend/tests/test_routers_smoke.py`
- **Steps:**
  1. Call `house_polls.seed_districts(db)` against an empty table; assert it still inserts
     all 60 `COMPETITIVE_DISTRICTS` rows with the same field values as before (unchanged
     function, regression check only)
  2. `GET /api/polls/house/districts`
- **Expected Result:** `seed_districts` behaviour and row count are unchanged; the districts
  endpoint still returns Cook ratings and centroids sourced from `CompetitiveDistrict` exactly
  as before this ticket

### TC-11 — A `District N` heading with no general-Polling descendant is a clean skip (covers AC-7)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Steps:**
  1. Call `house_polls._iter_polling_sections(_sections(PA_SECTIONS))` (District 9 has only
     a primary Polling section, no `General election` heading at all)
  2. With `caplog` at WARNING level, call `await house_polls.fetch_district_polls(db)` using
     `PA_SECTIONS`
- **Expected Result:** district 9 is absent from the enumerator's output; no wikitext request
  is made for district 9 (assert via `respx_router` call inspection — no request whose
  `section` param matches a District-9 index); no warning is logged for district 9; the run
  completes and is not considered degraded (mirrors the pre-existing
  `test_district_without_polling_is_skipped_not_errored` expectation, now exercised through
  the enumerator)

### TC-12 — One state's failure never starves the other 49 (covers AC-8)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** reuse `test_one_state_failure_does_not_block_others`'s responder — OH 404s with
  `missingtitle`, PA succeeds
- **Steps:**
  1. With `caplog` at WARNING level, call `await house_polls.fetch_district_polls(db)`
  2. Query `HousePoll` for PA and for OH
- **Expected Result:** PA's polls are still inserted; OH contributes zero rows; a warning
  naming OH and the reason is logged; no exception propagates out of `fetch_district_polls`
  — this is the existing test, re-asserted against the `STATE_NAMES`-driven loop instead of
  the `CompetitiveDistrict`-driven one

### TC-13 — Zero resolved sections across all 50 states raises (covers AC-9)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** mock every state's sections response to return a section list with no
  `District N` heading and no top-level `General election → Polling` (e.g. just `Overview`
  and `See also`)
- **Steps:**
  1. Call `await house_polls.fetch_district_polls(db)`
- **Expected Result:** raises `RuntimeError` (message identifies zero districts/sections
  resolved), matching the `economist_yougov` precedent
  (`test_refresh_raises_when_both_sources_return_nothing`); no partial commit is left in an
  inconsistent state

### TC-14 — Zero coverage records a `SourceRun` failure end-to-end through the scheduler (covers AC-9)
- **Type:** integration, `backend/tests/test_house_polls.py` (or alongside
  `test_scheduler_registration.py`, matching where `test_economist_yougov.py` places its
  scheduler-level case)
- **Setup:** `monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)`;
  `monkeypatch.setattr(db, "close", lambda: None)`; mock every state's sections response to
  resolve zero polling sections (same shape as TC-13); generic ballot section mocked to
  return normally (so the failure is isolated to the district-poll path)
- **Steps:**
  1. Call `await scheduler.refresh_house_polls()`
  2. Query `SourceRun` filtered by `source_id="house_polls_job"`
- **Expected Result:** `status="failure"`, `item_count` is `None`, `error_message` is
  non-empty and describes zero coverage — never `status="success"` with `item_count: 0`,
  which is the exact pattern that hid #10 and #15
- **Note:** per the implementation plan's accepted trade-off, this also means a run where the
  generic ballot succeeded is still recorded as a job failure, since both streams share one
  `SourceRun` row — assert the generic ballot's rows were still committed (query
  `GenericBallotAggregate`) even though the row is marked failed, to confirm nothing is lost

### TC-15 — A partial run (some states succeed, some fail or resolve nothing) is still a success (covers AC-10)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Setup:** PA resolves sections normally (2 districts yield); OH 404s; every other state
  resolves sections with zero matching districts
- **Steps:**
  1. Call `await house_polls.fetch_district_polls(db)` directly — assert it returns normally
     (no raise) and returns a nonzero count
  2. Separately, through `scheduler.refresh_house_polls()` with the same mocks and the
     `SessionLocal`/`close` monkeypatches from TC-14, query `SourceRun` for
     `source_id="house_polls_job"`
- **Expected Result:** the service call returns normally; the `SourceRun` row shows
  `status="success"` — AC-9's raise fires only on total-zero, so PA's one working state is
  enough to keep the job green

### TC-16 — Re-runs stay idempotent after the rewrite; existing rows keep their `poll_id` (covers AC-11)
- **Type:** unit, `backend/tests/test_house_polls.py`
- **Steps:** run the existing `test_rerun_is_idempotent_and_additive` body unchanged, but
  with `CompetitiveDistrict` left empty (no `_seed_district(db, "PA", 8)` call) — the point of
  this case is that idempotency no longer depends on district seeding at all
- **Expected Result:** run 1 inserts 3 PA-8 rows; run 2 against identical upstream data
  inserts 0 new rows and the 3 `poll_id`s are unchanged; run 3 with a 4th upstream poll added
  inserts exactly 1 new row and leaves the original 3 `poll_id`s untouched — same assertions
  as the pre-existing test, now proving the property holds without `CompetitiveDistrict`
  seeding

### TC-17 — No contract change in response shape, migrations, or job registration (covers AC-12)
- **Type:** integration, `backend/tests/test_routers_smoke.py` and
  `backend/tests/test_scheduler_registration.py`
- **Steps:**
  1. Seed one Wikipedia-sourced `HousePoll` row and one `CompetitiveDistrict` row; call
     `GET /api/polls/house` and `GET /api/polls/house/districts`; diff response field names
     against the pre-change shape (existing smoke assertions should already cover this —
     re-run them unmodified)
  2. Run `test_scheduler_registration.py`'s existing drift check and confirm `house_polls_job`
     is still present with `cadence_minutes=360` in `SOURCE_CADENCE` and still registered in
     `start_scheduler()`
  3. `grep -r "alembic" ` for a new migration touching `HousePoll`/`CompetitiveDistrict` —
     confirm none exists
  4. Confirm no file under `frontend/` is part of this change (diff review, not a runtime
     assertion)
- **Expected Result:** both endpoints return byte-identical field structure to before (only
  row counts differ); `house_polls_job` keeps its id and 360-minute cadence; no new Alembic
  revision; no frontend diff

## Edge Cases & Failure Modes
- Wikipedia heading-vocabulary drift across independently-edited pages → not directly
  testable against live Wikipedia; AC-9/TC-13 is the guard that makes a vocabulary-wide
  regression visible instead of silent
- A state page that 404s vs. one that returns malformed JSON vs. one whose section tree
  raises during enumeration → all three must be caught by the same per-state `try/except`
  (TC-12 covers the 404 case explicitly; the plan does not call for a distinct fixture per
  failure mode since all three land in the same `except Exception` handler)
- At-large page with both a primary and a general `Polling` section (Alaska, per the
  `ak_house_sections.json` fixture) → covered by TC-6 for title resolution and TC-7 for
  enumeration correctly yielding `(0, 26)` and never the primary's index (19)
- New districts appearing mid-cycle → no dedicated test; this is the steady-state behavior
  enumeration already produces on every run, not a special case

## Regression Check
- `test_house_polls.py`'s full existing suite (TC-0a/TC-0b plus
  `test_extract_polls_from_polling_section`, `test_missing_page_is_logged`,
  `test_one_state_failure_does_not_block_others`, `test_rerun_is_idempotent_and_additive`)
  must still pass — none of `_fetch_section_wikitext`, `_extract_polls_from_polling_section`,
  or `_parse_wiki_date` change in this ticket
- `test_scheduler_registration.py` — `house_polls_job` drift check still passes with no id or
  cadence change
- `test_routers_smoke.py` — `/api/polls/house*` smoke assertions still pass unmodified
- Full suite (`cd backend && pytest`) — currently 98 passing per the implementation plan;
  should grow by the new cases above and stay green

## Sign-off
- [ ] All test cases pass (`pytest backend/tests/` — this ticket has no manual/frontend
      cases, so full pytest green is the complete bar)
- [ ] Samuel has reviewed results before merge to main
