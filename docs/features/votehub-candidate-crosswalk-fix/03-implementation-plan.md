# Implementation Plan: VoteHub district-poll candidate crosswalk fix

**Slug:** `votehub-candidate-crosswalk-fix` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

Replace `_normalize_name`'s sorted-token exact-equality test with a structural comparison:
fold diacritics, split each FEC name into `(surname_tokens, given_tokens)` on its comma, and
match when the FEC surname's tokens form a **contiguous suffix** of the VoteHub name's tokens
and the first given names agree — falling back to surname-suffix-only when that surname selects
exactly one candidate in the district. Normalize at-large seats to district `0`, and log one
aggregate outcome summary per run. AC-9 (never guess) and AC-11 (never read `partisan`) are
unchanged. No model change, no migration, no frontend change.

**Measured effect** (proposed matcher run against the live feed and live FEC data,
2026-09-12): **30 stored today → 67 stored, +37 polls.**

## Backend Changes

*(Python 3.9 locally — use `Optional[...]`, not `X | Y`)*

All changes are in one file: `backend/app/elections/services/votehub.py`.

| Symbol | Change |
|---|---|
| `_fold(s)` | **New.** Unicode NFD, drop combining marks (`unicodedata.category(c) != "Mn"`), lowercase, punctuation → space. This is what makes `María Elvira Salazar` match `Salazar, Maria Elvira` (AC-3). Neither stored value is mutated. |
| `_tokens(name)` | **New.** `_fold` then split, dropping the suffix set. Extend the existing `_NAME_SUFFIXES` with honorifics seen live in FEC data (`mr`, `mrs`, `ms`, `dr` — e.g. `Pautsch, David Alfred Mr.`). |
| `_fec_name_parts(name)` | **New.** Returns `(surname_tokens, given_tokens)`. FEC stores `Last, First Middle`, so split on the **first comma**: everything before it is the surname (possibly several tokens), everything after is given names. No comma → treat the last token as the surname. |
| `_normalize_name` | **Remove.** Its sorted-token equality is the root cause; nothing should keep calling it. |
| `_district_candidates(db, state, district)` | Return the district's candidates as a list of `(name, party)` rather than a `normalized-name → parties` dict. The matching rules need the structured name parts, which a pre-flattened key throws away. Same query, same `Candidate.party` skip. |
| `_match_candidate_party(name, candidates)` | Rewrite per the rules below. Signature changes from `(name, crosswalk_dict)` to `(name, candidate_list)`. |
| `_parse_seat(seat)` | Add `AT_LARGE_STATES = frozenset({"AK", "DE", "ND", "SD", "VT", "WY"})`; when the state is in that set, return district `0` regardless of whether VoteHub sent `-AL` or `-01`. Fixes all 7 AK-01 drops (AC-7). |
| `fetch_votehub_house_polls(db)` | Adapt to the new `_district_candidates` return type. Add an outcome `Counter` and log one summary line at the end (AC-9). Keep the per-poll WARNINGs. |

### The matching rules, precisely (AC-1, AC-2, AC-2b, AC-4, AC-5)

Given VoteHub tokens `vt` and, for each stored candidate, FEC `(sur, giv)`:

1. A candidate is a **surname candidate** when `vt[-len(sur):] == sur` — the FEC surname's
   tokens are a contiguous suffix of the VoteHub name.
2. It is an **exact candidate** when it is a surname candidate *and* `vt[0] == giv[0]` (first
   given names agree) *and* there is at least one token before the surname suffix.
3. Resolve to the party of the single exact candidate. More than one exact candidate → `None`.
4. No exact candidate → resolve to the party of the single surname candidate. Zero or more
   than one → `None`.

**Do not derive the surname by taking the last token of the VoteHub name.** That is the
defect AC-2b exists to prevent: it yields `cruz` for `Monica De La Cruz`, `orden` for
`Derrick Van Orden`, `perez` for `Marie Gluesenkamp Perez`, `meeks` for
`Mariannette Miller-Meeks`, `wilpert` for `Marni von Wilpert`. Eleven drops have this shape —
the largest single bucket. The suffix test in rule 1 handles them without special cases.

Rule 3's strictness was checked: a looser variant resolving when several matched candidates
merely *agree* on a party stores the identical set of polls, so there is no coverage argument
for relaxing it (AC-5 note).

### The run summary (AC-9)

One `logger.info` at the end of `fetch_votehub_house_polls` carrying: returned, skipped for
unparseable `seat_name`, skipped for `<2` answers, inserted, updated, and skipped by cause
(`unresolved`, `ambiguous`, `generic_label`). Today every skip logs individually and nothing
counts them, which is why a 64% drop rate read as a healthy run. Keep the per-poll WARNINGs —
they carry the unmatched names, which is what makes a regression diagnosable.

Generic-label answers (`"Rep"`, `"Dem"`) get their own cause bucket so they are visibly
distinct from name-matching failures (AC-8). They remain skipped — decided 2026-09-12.

## Frontend Changes

None (AC-12).

## Data Model / Migration Notes

**No schema change and no migration.** The upsert key `f"votehub-{vid}"` is unchanged, so the
~37 newly-resolvable polls insert exactly once on the first post-deploy run and are updated in
place thereafter (AC-11).

`fetch_votehub_polls` (approval + generic ballot) and `compute_average` are untouched.
`compute_average` reads `VoteHubPoll`, not `HousePoll`, so no forecast input moves and
`test_staleness_regression.py`'s pin from #11 keeps passing (AC-12).

## Sequencing

1. `_fold`, `_tokens`, `_fec_name_parts`, extended suffix set. Pure functions — unit-test them
   directly against the real name pairs listed in AC-2b before wiring anything up.
2. `_parse_seat` at-large normalization. Independent of the matcher; verifiable on its own.
3. Rewrite `_district_candidates` + `_match_candidate_party`; delete `_normalize_name`.
4. Adapt `fetch_votehub_house_polls` to the new return type.
5. Add the outcome counter and summary line.
6. Add the AC-4b scope-gap detector test.
7. Full suite (`cd backend && pytest`), currently 98 passing.

### Test work

Extend `tests/test_votehub_house_polls.py`. The fixture
`tests/fixtures/votehub_us_representative.json` already exists — check whether it contains the
name shapes below and extend it if not, keeping it trimmed:

| Case | Shape needed |
|---|---|
| AC-1 | `Hurd, Jeffrey` ↔ `Jeffrey Hurd` |
| AC-2 | `Miller-Meeks, Mariannette Jane` ↔ `Mariannette Miller-Meeks` |
| AC-2b | `De La Cruz, Monica` ↔ `Monica De La Cruz`; `Van Orden, Derrick` ↔ `Derrick Van Orden` |
| AC-3 | `Salazar, Maria Elvira` ↔ `María Elvira Salazar` |
| AC-4 | `Hurd, Jeffrey` ↔ `Jeff Hurd` (nickname, unique surname) |
| AC-4 negative | two candidates sharing a surname, VoteHub given name matching neither → skip |
| AC-5 | two exact matches → skip, no party guessed |
| AC-6 | poll carrying `partisan: "DEM"` with unresolvable names → skip |
| AC-7 | `seat_name: "AK-01"` → stored `district == 0` |
| AC-8 | answers `["Rep", "Dem"]` → skipped, counted under `generic_label` |
| AC-11 | run twice → second run inserts nothing |

**AC-4b detector.** Needs a committed fixture of *all* FEC candidates filed in the districts
VoteHub polls (not a live call — the conftest autouse respx guard fails any un-mocked HTTP).
Capture it once from `GET /v1/candidates/?election_year=2026&office=H`, trim to
`(state, district_number, name, party_full, incumbent_challenge, has_raised_funds)`, and commit
as `tests/fixtures/fec_house_filed_2026.json`. The test asserts no polled district has a
surname unique among stored rows but ambiguous among all filed. Measured zero occurrences on
2026-09-12; a failure is the signal to promote roadmap #19, not to loosen AC-4.

## Documentation Updates

- [x] `SOURCES.md` — update the VoteHub row's district-poll note to describe the new matching
      rule (surname-suffix + first given name, diacritics folded).
- [ ] `.env.example` — no new env vars for this ticket. (Adding `FEC_API_KEY` there is a
      standing chore now parked with roadmap #19.)
- [x] `docs/ROADMAP.md` — #18 → shipped with the PR link, per `CLAUDE.md`.

## Risks / Rollback

| Risk | Mitigation |
|---|---|
| The surname-only fallback matches a minor candidate sharing a surname with the polled one | Scoped to a surname that selects exactly one candidate in the district. AC-4's negative case is a required test, and AC-4b detects the filtered-subset variant of this. |
| A relaxed matcher drifts into guessing on ambiguity | AC-5 and AC-6 are hard gates with their own test cases. Rule 3 returns `None` on multiple exact matches rather than picking one. |
| 37 more rows surface roadmap #12's cosmetic defects more widely | VoteHub rows are the *clean* ones — they populate `start_date`, `source_url` and `sample_size`, unlike the Wikipedia path. Low risk here. |
| Reviewers read the change as weakening AC-11 | It does not touch `partisan` at all. Worth saying so explicitly in the PR body, since the field sits right there in the payload. |

**Rollback:** single-file, no migration, no frontend — `git revert`. Rows inserted before a
revert keep their `votehub-{id}` keys and stay valid; the old matcher would simply stop
updating them.

**Second pair of eyes:** per `CLAUDE.md`'s merge exception, the surname-only fallback (rule 4)
is the one judgment call here. It is the largest recovery bucket and the loosest rule. Flag it
in the PR rather than auto-merging past it if the colliding-pair test needed any interpretation
to write.

## Test Plan Pointer

See `04-test-cases.md`.
