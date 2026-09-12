# Implementation Plan: District poll coverage driven by Wikipedia, not a hardcoded list

**Slug:** `district-coverage-from-wikipedia` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

`fetch_district_polls` stops asking the database which districts to scrape and asks Wikipedia
instead. One new enumerator walks a state page's already-fetched section list and yields every
`(district, section_index)` pair that has a `General election → Polling` descendant; the
existing single-district lookup becomes a thin wrapper over it so its tests keep passing
untouched. `_state_wiki_page` learns that six single-district states use a singular page title.
Everything downstream — wikitext fetch, table extraction, `poll_id` hashing, insert-only
upsert — is unchanged. No model change, no migration, no frontend change.

## Backend Changes

*(Python 3.9 locally — use `Optional[...]`, not `X | Y`)*

All changes are in one file: `backend/app/elections/services/house_polls.py`.

| Symbol | Change |
|---|---|
| `AT_LARGE_STATES` | **New** module constant: `frozenset({"AK", "DE", "ND", "SD", "VT", "WY"})`. The six single-district states. Note MT is *not* one (Montana regained a second seat in 2022 and MT-1 is in the current seed list). |
| `_state_wiki_page(state)` | Use `"election"` instead of `"elections"` when `state in AT_LARGE_STATES`. Verified live 2026-09-12: `2026_United_States_House_of_Representatives_election_in_Alaska` returns 200; the plural form returns `missingtitle`. Deliberately an explicit set, **not** a retry-on-404 fallback, so a genuine 404 on a multi-district state still surfaces as a warning (AC-8) instead of being masked by a second attempt. |
| `_iter_polling_sections(sections)` | **New.** Yields `(district_number, section_index)` for every `District N` heading whose block contains a `General election → Polling` descendant. Lifts the block-boundary and descendant logic out of `_find_polling_section` verbatim — same `toclevel` walk, same AC-2b guard — and runs it over every `District N` match rather than the first. If the page has **no** `District N` heading at all, look for a top-level `General election → Polling` and yield `(0, index)` (AC-5). |
| `_find_polling_section(sections, district)` | Reimplement as `dict(_iter_polling_sections(sections)).get(district)`. Keeps the existing public behaviour and signature so `tests/test_house_polls.py` TC-1/TC-7 pass unmodified, and guarantees the enumerator and the lookup can never disagree. |
| `fetch_district_polls(db)` | Iterate `STATE_NAMES` (all 50) instead of `db.query(CompetitiveDistrict).all()`. Drop the `by_state` `defaultdict`. Inner loop becomes `for district, section_idx in _iter_polling_sections(sections):` — no `_find_polling_section` call, no `if section_idx is None` skip (the enumerator only yields resolvable ones). Count resolved sections across all states in a local `resolved` counter; after the commit, `raise RuntimeError(...)` if `resolved == 0` (AC-9). Keep the per-state `try/except` exactly as-is (AC-8). |

Untouched, deliberately: `seed_districts`, `COMPETITIVE_DISTRICTS`, `_fetch_state_sections`,
`_fetch_section_wikitext`, `_extract_polls_from_polling_section`, `_housepoll_from_extract`,
`_parse_wiki_date`, the `poll_id` hash, `fetch_generic_ballot`, `_persist_generic_ballot`, and
`refresh_house_polls`'s call order. The `CompetitiveDistrict` import stays — `seed_districts`
still uses it.

**Upstream:** Wikipedia `action=parse`, unauthenticated, no key. Request count in the
section-list phase is unchanged at 50; the wikitext phase goes from ~31 useful of 60 attempted
to ~86 useful of 86 attempted, so total requests fall slightly. Failure isolation is the
existing per-state `try/except`.

### One consequence to accept explicitly

`house_polls_job` covers **both** the generic ballot and district polls, and they share one
`SourceRun` row. AC-9's raise therefore marks the whole job failed even when the generic
ballot succeeded. That is the intended trade — it is the same choice `economist-discovery-fix`
(#10) made, and the generic-ballot rows are already committed by then, so no data is lost.
Splitting the job into two `SourceRun` ids would be the alternative and is **out of scope**;
if it is ever wanted, it belongs with `scheduler-split` (T2).

## Frontend Changes

None. `DistrictMap` and `PollCarousel` render whatever rows exist, and
`GET /api/polls/house*` response shapes do not change (AC-12).

## Data Model / Migration Notes

**No schema change and no migration.** Upsert semantics are untouched: the Wikipedia path
stays insert-only, keyed on `wiki-{state}-{district}-{md5(state+district+pollster+dates+dem+rep)}`.
Because the hash inputs do not change, districts already scraped keep their existing
`poll_id`s and do not re-insert under new ids (AC-11).

At-large rows store `district = 0`, which is the convention `_cand_district`
(`backend/app/elections/routers/polls.py:30-32`) and FEC's `district_number` already use, so
`/api/polls/house/districts` joins them correctly with no route change.

## Sequencing

1. `AT_LARGE_STATES` + `_state_wiki_page` change. Smallest, independently verifiable: the six
   states stop logging `missingtitle`.
2. `_iter_polling_sections`, with `_find_polling_section` rewritten as a wrapper over it. Run
   the existing `tests/test_house_polls.py` **before** touching `fetch_district_polls` — TC-1
   and TC-7 must still pass unchanged. That is the regression gate for the whole refactor.
3. Capture the new fixture (see below) and add the enumeration + at-large tests.
4. Rewrite `fetch_district_polls`'s loop to iterate `STATE_NAMES` and consume the enumerator.
5. Add the `resolved == 0` raise and its test.
6. Full suite (`cd backend && pytest`), currently 98 passing.

### Fixture work (step 3)

`tests/fixtures/` already holds `pa_house_sections.json` (multi-district, District 8 general
Polling at index 141) and `ny17_house_sections.json` (primary-only Polling). Reuse both:

- `pa_house_sections.json` → enumeration returns several districts including 8 → 141.
- `ny17_house_sections.json` → NY-17 is **not** yielded (AC-3 under enumeration; this is the
  case a rewrite is most likely to regress).
- **New** `ak_house_sections.json`, trimmed from the live Alaska page captured 2026-09-12:
  `General election` at toclevel 1 with `Polling` at index 26, **and** a `Primary election`
  section with its own `Polling` at index 19. Enumeration must yield exactly `(0, 26)` — this
  single fixture covers AC-4, AC-5 and AC-3-on-an-at-large-page together.

Mock Wikipedia with `respx_router`, per the conftest autouse network guard and the existing
patterns in `test_house_polls.py`.

## Documentation Updates

- [x] `SOURCES.md` — update the "House district polls" row: the Wikipedia stream is now driven
      by the section tree across all 50 state pages, not by `CompetitiveDistrict`. Also fix
      that file's stale "Python runtime is 3.9" line while in there (standing chore).
- [ ] `.env.example` — no new env vars.
- [x] `docs/ROADMAP.md` — #17 → shipped with the PR link, per `CLAUDE.md`.

## Risks / Rollback

| Risk | Mitigation |
|---|---|
| The enumerator regresses AC-2b and starts ingesting primary polling as general | Step 2's ordering: existing TC-7 must pass before `fetch_district_polls` changes. `_find_polling_section` delegating to the enumerator means one implementation, one behaviour. |
| Coverage jumps and surfaces roadmap #12's cosmetic defects on many more districts | Expected and accepted — #12 owns it. Worth a look at the district map after deploy, but not a blocker. |
| The `resolved == 0` raise fires on a transient Wikipedia-wide outage | It is meant to. A total outage is exactly the condition that should record a `SourceRun` failure; the next 6h tick recovers on its own. |
| At-large page titles change form | The explicit set makes that a loud `missingtitle` warning for those six states rather than a silent miss. |

**Rollback:** single-file, no migration, no frontend — `git revert` the commit. The job keeps
its id and cadence throughout, so `SOURCE_CADENCE` and `/api/status/sources` are unaffected
either way. Rows inserted before a revert stay valid and keep their `poll_id`s.

## Test Plan Pointer

See `04-test-cases.md`.
