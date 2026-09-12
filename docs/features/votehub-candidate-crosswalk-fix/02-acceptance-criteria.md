# Acceptance Criteria: VoteHub district-poll candidate crosswalk fix

**Slug:** `votehub-candidate-crosswalk-fix` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: FEC legal-name ordering still matches VoteHub's
- **Given** an FEC candidate stored as `Hurd, Jeffrey` and a VoteHub answer choice
  `Jeffrey Hurd` for the same district
- **When** `fetch_votehub_house_polls(db)` resolves that poll
- **Then** the two match — the `Last, First` / `First Last` reordering that
  `district-poll-scraper-fix` already handled must keep working

### AC-2: An extra middle name or initial on either side still matches
- **Given** an FEC candidate stored as `Miller-Meeks, Mariannette Jane` and a VoteHub answer
  choice `Mariannette Miller-Meeks` (16 real drops on 2026-09-12 had this shape)
- **When** the poll is resolved
- **Then** the two match on surname plus first given name; a token present on one side and
  absent on the other must not cause a miss
- **And** the reverse also holds (VoteHub carrying a middle token FEC lacks)

### AC-2b: Compound and particle surnames match correctly
- **Given** FEC candidates whose surname is more than one token — `De La Cruz, Monica`,
  `Van Orden, Derrick`, `Gluesenkamp Perez, Marie`, `Miller-Meeks, Mariannette Jane`,
  `von Wilpert, Marni` — and VoteHub answer choices `Monica De La Cruz`, `Derrick Van Orden`,
  `Marie Gluesenkamp Perez`, `Mariannette Miller-Meeks`, `Marni von Wilpert`
- **When** each poll is resolved
- **Then** all of them match
- **And** the implementation must NOT derive a surname by taking the last token of the
  VoteHub name — that yields `cruz`, `orden`, `perez`, `meeks`, `wilpert` and fails every
  case above. Match by treating the FEC surname's tokens as a contiguous **suffix** of the
  VoteHub name's tokens instead.
- **Why this is its own criterion:** measured 2026-09-12, this shape accounts for 11 of the
  residual failures under a last-token implementation — the single largest recovery bucket in
  this ticket and the easiest rule to get wrong.

### AC-3: Diacritics do not defeat a match
- **Given** an FEC candidate stored as `Salazar, Maria Elvira` and a VoteHub answer choice
  `María Elvira Salazar`
- **When** the poll is resolved
- **Then** the two match — both sides are compared with combining marks stripped (Unicode
  NFD fold), and neither stored value is mutated

### AC-4: A nickname resolves only via a unique surname
- **Given** a VoteHub answer choice `Jeff Hurd` whose given name does not match FEC's
  `Jeffrey`, and exactly one candidate with the surname `Hurd` in that district's **stored**
  `Candidate` rows
- **When** the poll is resolved
- **Then** it matches that candidate by surname
- **And given** a district where two stored candidates share the surname `Garcia` and the
  VoteHub given name matches neither, **then** the surname fallback returns `None` and the
  poll is skipped — the fallback applies only to a surname unique within that district,
  never to a collision

**Scope of "unique", stated deliberately (decided 2026-09-12).** Uniqueness is asserted
against the **stored** `Candidate` rows for that district, not against every candidate filed
with the FEC. These differ: `fetch_house_candidates` filters on
`incumbent == "I" or (state, district) in competitive_keys or has_raised_funds`
(`fec_candidates.py:217`), which excluded 1,011 of 3,648 filed House candidates as of
2026-09-12. A surname can therefore be unique among stored rows while colliding with a
filtered-out filer, which would make this criterion's guarantee narrower than it reads.

Measured before accepting that: across all 48 districts VoteHub polls and all 161
candidate-name answers in them, the stored-unique / filed-ambiguous case occurs **zero
times**. Widening the scope would block nothing and would *recover* three matches
(`Brennan Barrington` OH-15, `Lupe Castillo` IL-04, `Chris Schmidt` NY-21 — all filed with
FEC, all filtered out of our table). Doing it properly requires storing the full filed set
behind a display-eligibility flag, because `DistrictOut.candidates` (`polls.py`) feeds the
district map — a model change and an Alembic migration. That is deliberately deferred to
roadmap #19 rather than widening this ticket before the election. AC-4b is what keeps the
deferral honest.

### AC-4b: The uniqueness scope gap is detected if it ever appears
- **Given** the stored `Candidate` subset and the full set of FEC candidates filed in the
  same district
- **When** the test suite runs
- **Then** a test asserts that no district currently polled by VoteHub has a surname that is
  unique among stored rows but ambiguous among all filed candidates — the condition that
  would silently turn AC-4's fallback into a wrong match
- **And** the test uses a committed fixture of filed candidates rather than a live FEC call,
  so it respects the suite's autouse respx network guard
- **And** if it ever fails, that is the signal to promote roadmap #19 rather than to loosen
  AC-4

### AC-5: Ambiguity still loses (AC-9 of `district-poll-scraper-fix` preserved)
- **Given** an answer choice that resolves to more than one candidate of differing parties
  under any of the rules in AC-1 through AC-4
- **When** the poll is resolved
- **Then** `None` is returned for that name, the poll is skipped, and no party is guessed —
  this ticket trades zero-match failures for coverage and must never trade ambiguous-match
  failures for coverage
- **Note (measured 2026-09-12):** a looser variant that resolves when several matched
  candidates *agree* on a party was tested and stores the identical set of polls, so the
  strict candidate-uniqueness reading above is adopted with no coverage cost

### AC-6: `partisan` is never consulted (AC-11 of `district-poll-scraper-fix` preserved)
- **Given** a poll carrying a `partisan` value (e.g. `"DEM"`) whose candidate names cannot be
  resolved
- **When** the poll is resolved
- **Then** it is skipped; `partisan` must not appear anywhere in the party-resolution path,
  including as a tie-breaker or a last-resort fallback

### AC-7: At-large seats resolve to district 0
- **Given** VoteHub sends `seat_name: "AK-01"` for the at-large Alaska seat while FEC stores
  those candidates with `district_number = 0` (the cause of all 7 AK-01 drops on 2026-09-12)
- **When** the poll is resolved
- **Then** the seat normalizes to district `0` before the crosswalk lookup, the crosswalk is
  non-empty, and the stored `HousePoll.district` is `0` — consistent with `_parse_seat`'s
  existing `AK-AL` → `0` mapping and with `_cand_district` in `polls.py:30-32`

### AC-8: Generic party labels are skipped, and counted as their own cause
- **Given** a poll whose answer choices are `"Rep"` and `"Dem"` rather than candidate names
  (9 such polls on 2026-09-12)
- **When** the poll is resolved
- **Then** it is skipped — **decided 2026-09-12: out of scope for v1**, because these are
  generic-ballot-shaped questions rather than named head-to-heads and storing them as
  ordinary `HousePoll` rows would make the district surfaces compare unlike things
- **And** the skip is attributed to a distinct "generic label" cause in the AC-9 summary, so
  it is visibly different from a name-matching failure

### AC-9: The skip rate is observable in one place
- **Given** a completed `fetch_votehub_house_polls(db)` run
- **When** the run finishes
- **Then** it logs a single summary line carrying: polls returned, dropped for unparseable
  `seat_name`, dropped for fewer than two answers, stored (inserted and updated), and skipped
  broken down by cause (unresolved name, ambiguous, generic label)
- **And** the existing per-poll WARNING with the unmatched names is retained — the gap today
  is that nothing aggregates them, so a 64% drop rate read as a healthy run

### AC-10: Polls with no usable seat or too few answers are still skipped
- **Given** a poll with `seat_name: null` (8 on 2026-09-12) or fewer than two answers
- **When** the poll is resolved
- **Then** it is skipped and logged as today — this ticket does not attempt to recover them

### AC-11: Re-runs are idempotent
- **Given** a database already holding `votehub-{id}` `HousePoll` rows
- **When** `fetch_votehub_house_polls(db)` runs twice in a row
- **Then** the second run inserts nothing new, updates the existing rows in place, and
  creates no duplicates; a poll that becomes newly resolvable under AC-1 through AC-7
  inserts exactly once

### AC-12: The rest of the VoteHub service is untouched
- **Given** this change is deployed
- **When** `fetch_votehub_polls(db)` (approval + generic ballot) and
  `compute_average(db, ...)` run
- **Then** their behaviour and return values are unchanged — `compute_average` reads
  `VoteHubPoll`, not `HousePoll`, so no forecast input moves and the
  `poll-staleness-labels` (#11) regression pin still passes
- **And** no Alembic migration exists for this ticket, `votehub_job` keeps its id and hourly
  cadence so `SOURCE_CADENCE` is unchanged, and no frontend file is modified

### AC-13: A total upstream failure is still a failure
- **Given** the `us-representative` request errors, returns a non-2xx, or returns a
  non-list body
- **When** `refresh_votehub` runs
- **Then** the existing behaviour is preserved: the failure is logged and the approval and
  generic-ballot streams in the same job are unaffected — one stream failing must not starve
  the other

## Data Quality / Edge Cases

- **Upstream unavailable / malformed:** AC-13. The district path and the
  approval/generic-ballot path must stay independently failable within `refresh_votehub`.
- **First run vs. re-run:** AC-11. The upsert key `votehub-{id}` is unchanged, so the ~45
  newly-resolvable polls insert once on the first post-deploy run and are updated in place
  thereafter.
- **A candidate missing from our `Candidate` rows:** 4 drops on 2026-09-12 were names that
  did not resolve at all. **Corrected 2026-09-12:** only one is genuinely absent from FEC —
  the other three (`Brennan Barrington` OH-15, `Lupe Castillo` IL-04, `Chris Schmidt` NY-21)
  are filed with FEC and were excluded by `fetch_house_candidates`' filter. All four remain
  skipped in v1; recovering the three is roadmap #19. See AC-4's scope note and AC-4b.
  Related coupling: `competitive_keys` in that filter comes from `CompetitiveDistrict`, so
  ticket #17's coverage work can widen this gap further. Measure after both ship rather than
  loosening the filter here.
- **Same-party and non-D-vs-R generals (4 polls, out of scope):** Alaska's ranked-choice and
  California's top-two systems can produce a general election with no Democrat-versus-
  Republican pairing at all — measured 2026-09-12: AK-AL (REP vs IND, twice), CA-06
  (DEM vs OTH), CA-40 (REP vs REP). `HousePoll` has only `dem` and `rep` columns, so these
  cannot be stored regardless of how well the names resolve. They resolve correctly and are
  then skipped for want of a D/R pair. Tracked as roadmap #20; no criterion here requires
  storing them.
- **Upstream sparsity:** VoteHub returns 92 district polls total, newest fieldwork
  2026-09-03, 4 within the last 14 days. This ticket recovers rows; it does not make the feed
  fresher, and no criterion should be written as though it does.
- **Rate limits / auth:** none — the VoteHub polls API is unauthenticated and the request
  count is unchanged (one call, full history, no pagination).

## Out of Scope

- Using VoteHub's `partisan` field (AC-6 forbids it).
- Guessing on ambiguity (AC-5 forbids it).
- Recovering the 8 null-`seat_name` polls or the 9 generic-label polls in v1 (AC-8, AC-10).
- Changing how FEC names are stored or loosening `fetch_house_candidates`' filter — roadmap
  #19 owns that, and AC-4b is the tripwire for it.
- Alerting on a high skip rate — the summary line and `SourceRun` are the surface, consistent
  with #13's reasoning that zero traffic makes alerting heavy-handed today.
- The Wikipedia district stream — roadmap #17 (`district-coverage-from-wikipedia`).
- Any change to `compute_average`, the forecast model, or `/api/polls/generic-ballot`.

## Sign-off
- [x] Samuel has reviewed and approved these criteria — approved 2026-09-12 in Cowork.
- **Stage 4 delegated:** `04-test-cases.md` is to be written by Claude Code as the first
  step of implementation, from these criteria. The criteria above are the source of truth;
  if a case cannot be written against one, stop and raise it rather than reinterpreting it.
