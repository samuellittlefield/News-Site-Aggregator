# Test Cases: VoteHub district-poll candidate crosswalk fix

**Slug:** `votehub-candidate-crosswalk-fix` &nbsp; **Source:** `02-acceptance-criteria.md`

> All cases are backend pytest, extending `backend/tests/test_votehub_house_polls.py`'s
> existing pattern (`db`/`respx_router` fixtures, autouse network guard per `conftest.py`).
> No frontend surface changes in this ticket (AC-12), so there is no manual/click-through
> section. The name-shape table in `03-implementation-plan.md`'s "Test work" section is the
> source for the fixture pairs used below. New fixtures: extend
> `tests/fixtures/votehub_us_representative.json` with the additional polls TC-1 through
> TC-11 need; add `tests/fixtures/fec_house_filed_2026.json` for TC-7 (AC-4b).

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-0a, TC-1 |
| AC-2 | TC-0a, TC-2 |
| AC-2b | TC-0b, TC-3 |
| AC-3 | TC-0a, TC-4 |
| AC-4 | TC-5, TC-6 |
| AC-4b | TC-7 |
| AC-5 | TC-8 |
| AC-6 | TC-9 |
| AC-7 | TC-10 |
| AC-8 | TC-11 |
| AC-9 | TC-12 |
| AC-10 | TC-13 |
| AC-11 | TC-14 |
| AC-12 | TC-15 |
| AC-13 | TC-16 |

## Pure-Function Tests — build before wiring anything up (per implementation plan §Sequencing)

### TC-0a — `_fold` and `_tokens` normalize both formats to the same token list (covers AC-1, AC-2, AC-3)
- **Type:** unit, `backend/tests/test_votehub_house_polls.py`
- **Steps:**
  1. `votehub._fold("María Elvira Salazar")` → compare against `votehub._fold("Maria Elvira Salazar")`
  2. `votehub._tokens("Hurd, Jeffrey")` and `votehub._tokens("Jeffrey Hurd")`
  3. `votehub._tokens("Pautsch, David Alfred Mr.")` — confirm the honorific is dropped
- **Expected Result:** (1) diacritics-stripped and plain strings fold identically; (2) both
  sides tokenize to the same bag ignoring order (`{"hurd", "jeffrey"}`); (3) tokens are
  `["pautsch", "david", "alfred"]` — `mr` is dropped via the extended `_NAME_SUFFIXES`
  (`jr`, `sr`, `ii`, `iii`, `iv`, `v`, `mr`, `mrs`, `ms`, `dr`)

### TC-0b — `_fec_name_parts` splits on the first comma into `(surname_tokens, given_tokens)` (covers AC-2b)
- **Type:** unit, `backend/tests/test_votehub_house_polls.py`
- **Steps:**
  1. `votehub._fec_name_parts("Miller-Meeks, Mariannette Jane")`
  2. `votehub._fec_name_parts("De La Cruz, Monica")`
  3. `votehub._fec_name_parts("Van Orden, Derrick")`
  4. `votehub._fec_name_parts("Nolastname")` — no comma present
- **Expected Result:** (1) `(["miller", "meeks"], ["mariannette", "jane"])`; (2)
  `(["de", "la", "cruz"], ["monica"])`; (3) `(["van", "orden"], ["derrick"])`; (4) falls back to
  treating the last token as the surname, per the implementation plan's no-comma rule —
  `(["nolastname"], [])`
- **Automation note:** these four cases are the direct regression gate for AC-2b's "do not
  use the last token" defect — (1) and (2) both have a last token (`meeks`, `cruz`) that is
  only part of the real surname, so a last-token implementation would silently pass an assertion
  that checked only `sur[-1]` but fail the suffix match in TC-3

## Backend

### TC-1 — FEC `Last, First` still matches VoteHub `First Last` (covers AC-1)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** `Candidate("Hurd, Jeffrey", REP, CO, 3)`; VoteHub answer choice `"Jeffrey Hurd"`
- **Steps:** call `votehub._match_candidate_party("Jeffrey Hurd", [("Hurd, Jeffrey", "REP")])`
- **Expected Result:** returns `"REP"` — the pre-existing reordering case keeps working under
  the new matcher

### TC-2 — An extra middle name or initial on either side still matches (covers AC-2)
- **Type:** unit, `test_votehub_house_polls.py`
- **Steps:**
  1. `votehub._match_candidate_party("Mariannette Miller-Meeks", [("Miller-Meeks, Mariannette Jane", "REP")])`
  2. Reverse case: `votehub._match_candidate_party("Mariannette Jane Miller-Meeks", [("Miller-Meeks, Mariannette", "REP")])`
     — VoteHub carries a middle token FEC lacks
- **Expected Result:** both return `"REP"` — a token present on one side and absent on the
  other does not cause a miss, in either direction

### TC-3 — Compound and particle surnames match via contiguous suffix, not last token (covers AC-2b)
- **Type:** unit, `test_votehub_house_polls.py`
- **Steps:** for each pair below, call `votehub._match_candidate_party(votehub_name, [(fec_name, "DEM")])`
  and assert the result is `"DEM"`:
  | FEC name | VoteHub name |
  |---|---|
  | `De La Cruz, Monica` | `Monica De La Cruz` |
  | `Van Orden, Derrick` | `Derrick Van Orden` |
  | `Gluesenkamp Perez, Marie` | `Marie Gluesenkamp Perez` |
  | `Miller-Meeks, Mariannette Jane` | `Mariannette Miller-Meeks` |
  | `von Wilpert, Marni` | `Marni von Wilpert` |
- **Expected Result:** all five resolve to `"DEM"`
- **Automation note:** this is the direct AC-2b regression gate. Also assert, as a negative
  control proving the suffix rule (not a last-token rule) is what's implemented: taking just
  the last VoteHub token (`cruz`, `orden`, `perez`, `meeks`, `wilpert`) against the same FEC
  rows via `votehub._tokens(fec_name)[-1:]` would **not** equal the full surname token list for
  any of the five — i.e. assert `len(votehub._fec_name_parts(fec_name)[0]) > 1` for at least
  the first three, confirming the fixture actually exercises a multi-token surname and isn't
  accidentally single-token

### TC-4 — Diacritics do not defeat a match, and stored values are untouched (covers AC-3)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** `Candidate("Salazar, Maria Elvira", REP, FL, 27)`; VoteHub answer choice
  `"María Elvira Salazar"`
- **Steps:**
  1. `votehub._match_candidate_party("María Elvira Salazar", [("Salazar, Maria Elvira", "REP")])`
  2. Re-read the seeded `Candidate` row from the `db` session
- **Expected Result:** (1) returns `"REP"`; (2) `Candidate.name` is still exactly
  `"Salazar, Maria Elvira"` — folding happens only in the comparison, never mutates stored data

### TC-5 — A nickname resolves via a surname unique within the district (covers AC-4)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** seed only `Candidate("Hurd, Jeffrey", REP, CO, 3)` and one DEM opponent with a
  distinct surname; VoteHub poll for CO-03 with answer choice `"Jeff Hurd"`
- **Steps:** run `fetch_votehub_house_polls(db)`
- **Expected Result:** the poll is stored with `rep` set from the Hurd/REP row — `"Jeff"` does
  not equal `"Jeffrey"` so this resolves through the surname-only fallback (rule 4), not the
  exact-match rule

### TC-6 — A colliding surname never falls back — poll is skipped (negative case for AC-4)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** seed two candidates sharing a surname in the same district —
  `Candidate("Garcia, Ana", DEM, TX, 28)` and `Candidate("Garcia, Luis", REP, TX, 28)`; VoteHub
  answer choice `"Maria Garcia"` (matches neither given name)
- **Steps:** run `fetch_votehub_house_polls(db)` with `caplog` at WARNING
- **Expected Result:** the poll is skipped (`saved == 0`, no `HousePoll` row for TX-28); the
  surname-only fallback (rule 4) sees two surname candidates and returns `None`; the WARNING
  names `"Maria Garcia"` as unresolved
- **Note:** per `CLAUDE.md`'s merge exception, if writing this case's assertions required any
  interpretation of "colliding pair" beyond a direct reading of AC-4, say so in the PR

### TC-7 — The stored-unique / filed-ambiguous scope gap has zero occurrences today (covers AC-4b)
- **Type:** unit, `test_votehub_house_polls.py`, using the new committed fixture
  `tests/fixtures/fec_house_filed_2026.json` (no live HTTP — respected by the autouse respx
  guard)
- **Setup:** the fixture holds the full filed-candidate set (trimmed to `state`,
  `district_number`, `name`, `party_full`, `incumbent_challenge`, `has_raised_funds`) for every
  district covered by `votehub_us_representative.json`'s polls; the `db` session is seeded with
  only the subset of those rows that `fetch_house_candidates`' filter
  (`incumbent == "I" or (state, district) in competitive_keys or has_raised_funds`) would keep
- **Steps:**
  1. For every `(state, district)` pair appearing in `votehub_us_representative.json`, compute
     the set of FEC surname-tokens (via `votehub._fec_name_parts`) from the **filed** fixture
     and from the **stored** `Candidate` rows separately
  2. Assert: no surname that is unique among the stored set for that district is *ambiguous*
     (maps to more than one candidate) among the filed set for the same district
- **Expected Result:** the assertion holds for every polled district — zero occurrences,
  matching the count measured live on 2026-09-12
- **Failure protocol:** if this ever fails, that is the signal to promote roadmap #19
  (`fec-filed-candidate-scope`), not to loosen AC-4 or delete this test

### TC-8 — Two exact matches is ambiguity, even if the plan's data never lands here with matching parties (covers AC-5)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** seed `Candidate("Smith, John Robert", DEM, OH, 15)` and
  `Candidate("Smith, John Michael", REP, OH, 15)`; VoteHub answer choice `"John Smith"` — both
  are surname candidates AND exact candidates (surname suffix matches, first given name `john`
  agrees with both)
- **Steps:** run `fetch_votehub_house_polls(db)` with `caplog` at WARNING
- **Expected Result:** the poll is skipped; no party is guessed; rule 3 fires (more than one
  exact candidate → `None`) rather than falling through to the surname-only rule; the WARNING
  names `"John Smith"`

### TC-9 — `partisan` is never consulted, including under the new matcher (covers AC-6)
- **Type:** integration + static, `test_votehub_house_polls.py` (extends the existing
  `test_partisan_field_is_never_used_as_party`, which stays but now runs against the rewritten
  matcher)
- **Steps:**
  1. Re-run the existing test body unchanged (fixture's `partisan: "DEM"`, first answer is REP)
  2. Keep the existing static guard: `inspect.getsource(votehub)` contains no `'partisan")'` or
     `'partisan"]'`
- **Expected Result:** unchanged from today — `rep == 46.0`, `dem == 39.0`, sourced from the
  `Candidate` crosswalk; the static guard still passes against the rewritten file

### TC-10 — At-large seats resolve to district 0 regardless of `-01` or `-AL` (covers AC-7)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** `Candidate("Begich, Nick", REP, AK, 0)`, `Candidate("Schultz, Matt", DEM, AK, 0)`
  — stored at district `0`, matching FEC's at-large convention; VoteHub poll with
  `seat_name: "AK-01"`
- **Steps:**
  1. `votehub._parse_seat("AK-01")` — call directly
  2. Run `fetch_votehub_house_polls(db)` end to end
- **Expected Result:** (1) returns `("AK", 0)`, not `("AK", 1)`; (2) the crosswalk lookup for
  AK district `0` is non-empty, the poll resolves, and the stored `HousePoll.district` is `0`
- **Automation note:** this replaces `AT_LARGE_STATES`-style guessing from seat text alone —
  confirm `votehub._parse_seat("AK-AL")` also returns `("AK", 0)` (pre-existing behavior,
  regression-checked here since `_parse_seat` is touched)

### TC-11 — Generic party-label answers are skipped and counted under their own cause (covers AC-8)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** VoteHub poll for a valid, parseable district (e.g. `NY-21`) whose `answers` are
  `[{"choice": "Rep", "pct": 48.0}, {"choice": "Dem", "pct": 45.0}]`; seed real NY-21
  candidates so a name-matching failure is not the reason for the skip
- **Steps:** run `fetch_votehub_house_polls(db)` with `caplog` at INFO (to capture the AC-9
  summary) and WARNING
- **Expected Result:** the poll is skipped; the run's aggregate summary line (TC-12) attributes
  it to a `generic_label` cause distinct from `unresolved`/`ambiguous` — assert on the summary
  line's content directly rather than inferring the cause from a per-poll WARNING alone

### TC-12 — One aggregate summary line reports every stage, per run (covers AC-9)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** a fixture combining, in one run: one poll with `seat_name: null` (bad seat), one
  with a single answer (`<2` answers), one that resolves and inserts, one that resolves and
  updates an already-stored row, one with an unresolved name, one ambiguous, and one generic-
  label (`["Rep", "Dem"]`)
- **Steps:** run `fetch_votehub_house_polls(db)` twice (second run to exercise the "updated"
  count) with `caplog` at INFO
- **Expected Result:** exactly one `INFO` summary line per run naming: returned, bad-seat,
  too-few-answers, inserted, updated, and skipped-by-cause counts for `unresolved`,
  `ambiguous`, and `generic_label` — the numbers in the line match the fixture's composition
  on each run; the pre-existing per-poll WARNINGs for the unresolved/ambiguous/bad-seat cases
  are still present (this is additive, not a replacement)

### TC-13 — Null `seat_name` and fewer-than-two answers are still skipped, unrecovered (covers AC-10)
- **Type:** integration, `test_votehub_house_polls.py` (regression check — behavior unchanged
  from before this ticket)
- **Setup:** one poll with `seat_name: null`, one with `answers` of length 1
- **Steps:** run `fetch_votehub_house_polls(db)`
- **Expected Result:** both are skipped, both produce a WARNING, neither is attempted against
  the crosswalk; the AC-9 summary (TC-12) attributes them to "bad seat" / "too few answers"
  respectively, not to a name-matching cause

### TC-14 — Re-runs are idempotent, including for a poll newly resolvable under the new matcher (covers AC-11)
- **Type:** integration, `test_votehub_house_polls.py` (extends the existing idempotency
  coverage in `test_votehub_house_poll_is_fetched_and_parsed`)
- **Setup:** a poll shaped like one of the AC-2b/AC-4 cases — unresolvable under the old
  sorted-token matcher, resolvable under the new one
- **Steps:**
  1. Run `fetch_votehub_house_polls(db)` — assert `saved == 1` and the row exists
  2. Run it again unchanged — assert `saved == 0` on the second call (no new insert) and the
     row's `poll_id` and field values are unchanged (an update, not a duplicate)
- **Expected Result:** first run inserts exactly once; second run updates in place; no
  duplicate `HousePoll` rows for the same VoteHub id

### TC-15 — The rest of the VoteHub service is byte-for-byte untouched (covers AC-12)
- **Type:** integration + regression, `test_votehub_house_polls.py` plus existing suites
- **Steps:**
  1. Run the existing `fetch_votehub_polls` (approval + generic-ballot) tests unmodified
  2. Run `compute_average` against a fixture of `VoteHubPoll` rows unmodified from before this
     ticket
  3. Run `backend/tests/test_staleness_regression.py` (the #11 pin) in full
  4. `grep -r "alembic"` for a new revision touching `HousePoll`/`Candidate` — confirm none
  5. Confirm no file under `frontend/` is part of the diff (diff review, not a runtime
     assertion)
- **Expected Result:** all pre-existing tests pass unmodified; the #11 regression pin
  (`swing_d`, `swing_source`, `dem_prob`, `rep_prob`, `median_dem_seats` for both chambers)
  is bit-identical; no new Alembic revision; no frontend diff

### TC-16 — A total upstream failure on the district-poll path does not starve approval/generic-ballot (covers AC-13)
- **Type:** integration, `test_votehub_house_polls.py`
- **Setup:** mock the `us-representative` request to return a 500 (or a non-list body); mock
  the approval/generic-ballot queries to succeed normally
- **Steps:** call `votehub.fetch_votehub_polls(db)` and `votehub.fetch_votehub_house_polls(db)`
  as the scheduler's `refresh_votehub` does — sequentially, independently try/excepted
- **Expected Result:** `fetch_votehub_house_polls` returns `0` and logs a WARNING; the
  approval/generic-ballot upserts still complete and their counts are unaffected — matches
  today's behavior, unchanged by this ticket

## Edge Cases & Failure Modes
- A VoteHub name with no comma-derivable surname structure and zero FEC candidates in that
  district → falls through to `None` cleanly (rule 4's "zero surname candidates" branch),
  same as today's zero-match case
- A district with `Candidate` rows for only one party (opponent not yet filed/funded) →
  a resolvable answer choice still stores; the unmatched opponent's answer contributes to the
  `unresolved` cause count without blocking the resolvable side, consistent with existing
  `dem_val is None or rep_val is None` skip-the-whole-poll behavior (unchanged: a poll is only
  stored when **both** dem and rep resolve)
- At-large states other than Alaska (`DE`, `ND`, `SD`, `VT`, `WY`) are not currently polled by
  VoteHub as of 2026-09-12, so TC-10 exercises AK only; no dedicated fixture for the other five
  since `_parse_seat`'s at-large handling is state-agnostic once implemented

## Regression Check
- `test_votehub_house_polls.py`'s pre-existing six tests must still pass (three are extended
  in place per TC-9/TC-14 above rather than duplicated)
- `test_staleness_regression.py` (#11 pin) — TC-15
- `test_scheduler_registration.py` — `votehub_job` keeps its id and hourly cadence, no drift
- `test_module_boundaries.py` — this ticket's one changed file
  (`elections/services/votehub.py`) stays inside the `elections` package; no new cross-package
  import introduced
- Full suite (`cd backend && pytest`) — currently 98 passing per the implementation plan;
  should grow by the new cases above and stay green

## Sign-off
- [ ] All test cases pass (`pytest backend/tests/` — this ticket has no manual/frontend
      cases, so full pytest green is the complete bar)
- [ ] Samuel has reviewed results before merge to main
