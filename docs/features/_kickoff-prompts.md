# Claude Code kickoff prompts

Written in Cowork 2026-09-11 after auditing production. Paste one bucket at a time into
Code mode. They're ordered — buckets 1–3 are the data fixes, 4–5 are the extraction.

**Spec status:** buckets 1–3 are bug fixes whose findings are specific enough to act as the
spec, and each prompt carries the evidence inline. **Bucket 4 has full pipeline docs** as of
2026-09-11. Bucket 5 still needs two decisions from Samuel and then its docs.

---

## Bucket 1 — Fix the Economist/YouGov discovery (blocker)

> Roadmap item #10, slug `economist-discovery-fix`.
>
> `economist_yougov.py` has silently stopped finding new reports. The newest row in
> `EconomistReport` is fieldwork 2026-07-25/27, fetched 2026-08-02 — 46 days stale as of
> 2026-09-11. The 12h scheduler job still runs and records `status: success` with
> `item_count: 0`, so nothing surfaces on the Data Sources panel.
>
> This is our discovery path, not YouGov going quiet. Proof: VoteHub carries a
> YouGov/Economist generic-ballot poll fielded 2026-09-04/08 whose source URL is
> `https://d3nkl3psvxxpe9.cloudfront.net/documents/econTabReport_SlcWdVd.pdf` — the same
> CloudFront host our Wikipedia-based discovery step walks. The reports are being published.
>
> Start by reproducing the failure: run the discovery step by hand against the live
> Wikipedia page and show me what it finds versus what's actually linked there. My guess is
> the page structure changed, the same way the district scraper broke before PR #8 — but
> confirm before fixing.
>
> Then fix it, and make the failure loud: if discovery returns zero candidate report URLs on
> a run, that should record as a failure on `SourceRun`, not a success with `item_count: 0`.
> A source that finds nothing where something exists is broken, and the panel should say so.
>
> Add tests under `backend/tests/` covering the parse against a fixture of the current page
> structure, and the zero-results-is-a-failure case. Follow the repo conventions in
> `CLAUDE.md` — PR, CI green, merge, then update `docs/ROADMAP.md` item #10 to shipped.

---

## Bucket 2 — Stop the Polls page showing misleading numbers

> Roadmap items #11 (`poll-staleness-labels`) and #12 (`district-poll-data-quality`). Two
> related problems, both cosmetic-but-credibility-damaging, both on the page a new visitor
> lands on. Do them together.
>
> **#11 — staleness labelling.** VoteHub's approval stream is lagging *upstream*, not in our
> ingest: `api.votehub.com/polls?poll_type=approval` returns 2,945 rows whose newest
> `end_date` is 2026-08-28, while their generic-ballot stream was current to 09-08 the same
> day. Don't try to fix `votehub.py` — there's nothing there to fix. The problem is that
> `ApprovalSection` presents a 5-poll, 21-day average with no indication of its age.
>
> Add fieldwork-date labelling to the poll cards — the approval card at minimum, ideally the
> generic ballot too, since the same problem will hit it eventually. Pick a staleness
> threshold and make the card visibly degrade past it rather than silently showing old
> numbers as current. Your call on whether that's a label, a muted state, or hiding the
> card; tell me what you chose and why.
>
> **#12 — district poll data quality.** The Wikipedia stream in `house_polls.py` is storing
> bad rows. As of 2026-09-11, out of 112 rows across 37 districts:
> - 3 rows have `end_date` in the future — 2026-09-28, 17 days out. A poll that hasn't
>   happened is in the carousel.
> - 82 of 112 rows are null on `start_date`, `source_url` and `sample_size` — every
>   Wikipedia-sourced row. No provenance to click through to.
> - Markup is bleeding into the pollster field. Real stored values include
>   `Emerson Collegename=NPI` and a string truncated mid-word at
>   `…National Republican Congressional Commi`.
> - Pollster-name variants defeat dedup: `SurveyUSA` and `Survey USA` don't collapse, giving
>   9 duplicate groups across 20 rows — same district, same numbers, same date, listed twice.
>
> Fix the parser, add a normalisation step for pollster names, reject future-dated polls at
> ingest, and write a migration or one-off cleanup for the rows already in prod. Tests for
> each of the four cases. Same convention loop as bucket 1.

---

## Bucket 3 — Teach `SourceRun` what stale means

> Roadmap item #13, slug `sourcerun-staleness`.
>
> `status: success` + `item_count: 0` is currently indistinguishable from broken. Three
> polling jobs show exactly that right now and only one of them is actually failing — I only
> caught it by comparing fieldwork dates against upstream by hand.
>
> This is structurally the same bug you fixed on 2026-07-21 in PR #11, one layer up. That fix
> taught the *forecast model* to report which fallback tier it landed on. The *ingestion*
> layer never learned the same lesson.
>
> `SourceRun` already stores `cadence_minutes`. Add a per-source expected-freshness threshold
> and make "ran clean but produced nothing new for N cycles" a distinct state from success —
> surfaced on the Data Sources panel alongside failing and stale. `SOURCE_CADENCE` is already
> the single source of truth shared by the scheduler and `GET /api/status/sources`; extend
> that rather than introducing a second config.
>
> Worth deciding explicitly: some sources legitimately return zero (the weekly issue tagger
> with no pending candidates). The threshold needs to distinguish "nothing to do" from
> "should have found something." Tell me how you drew that line.
>
> Same convention loop. This one closes the loop on the audit — after it ships, the next
> silent failure surfaces on the panel instead of needing a manual audit.

---

## Bucket 4 — Extraction T1 + T2 (backend seam + scheduler split)

**Specs are written.** All four docs exist for both features, approved 2026-09-11. Paste
this as-is.

> Implement extraction tickets T1 then T2. Read all four docs for each before writing
> code: `docs/features/elections-seam/` and `docs/features/scheduler-split/`. T2 depends
> on T1 being merged first — don't interleave them.
>
> **T1 (`elections-seam`)** regroups `backend/app/routers/` and `backend/app/services/`
> into `app/elections/`, `app/monitor/` and `app/shared/` (6/6/1 routers, 10/21/3
> services — the exact mapping is a table in the implementation plan), and splits
> `models.py` into a package. No behaviour change, no schema change, no frontend change.
>
> Two things in T1 will bite if you skim:
> - `Base` is declared exactly once, in a new `app/models/base.py`, moved from
>   `models.py` line 6. Not in `database.py` (it has none), not in `models/__init__.py`
>   (circular). Three modules each calling `declarative_base()` is the failure mode this
>   ticket is most likely to hit, and TC-5 is the test that catches it.
> - `alembic/env.py` line 23 does `from app.models import Base`. The new
>   `__init__.py` must re-export `Base` as well as the 25 model classes, or every
>   migration breaks while the obvious tests stay green (TC-7).
>
> The acceptance bar for T1 is an **empty** `alembic revision --autogenerate` diff plus
> a green suite whose only test-file edits are import paths. If you find yourself
> changing an assertion to make something pass, stop — the refactor altered behaviour
> and that's a failure, not a fix.
>
> **T2 (`scheduler-split`)** grows `SOURCE_CADENCE` into a full job registry and derives
> all three job enumerations from it, then gates registration by domain. The
> consolidation is the substance; the split falls out of it.
>
> Context worth having: the job set is currently enumerated in four hand-maintained
> places that already disagree — `SOURCE_CADENCE` (17), `start_scheduler` (17),
> `_startup_refresh` (15), `_do_full_refresh` (12). `_do_full_refresh` is what the
> public Refresh button calls, and it omits every election-side job, so clicking
> Refresh today refreshes no polling data. Fixing that is part of the ticket.
>
> `POST /api/refresh` stays public and cheap (monitor jobs only) and starts naming the
> domains it refreshed. Election jobs get `POST /api/refresh/elections` behind the
> existing `require_admin_key`, with an in-flight guard returning **409** on overlap —
> not 429, the problem is overlap rather than frequency. Reasoning is in the T2 feature
> plan's Open Questions; don't re-litigate it, but do flag it if implementation shows
> it's wrong.
>
> If time runs short, T2 steps 1-5 are a shippable unit on their own — they fix the
> live `/api/refresh` bug without the split.
>
> Both tickets: follow `CLAUDE.md` — PR, CI green, merge, then update `docs/ROADMAP.md`
> (T1/T2 → shipped with PR links). T1 also delivers the "autogenerate produces empty
> diff" chore from the roadmap's Later section, so strike that too. While you're in
> `SOURCES.md`, fix its stale "The Python runtime is 3.9" line — Railway and CI both
> run 3.11.

---

## Bucket 5 — Extraction T3 + T5a (frontend split + front door)

> **Needs pipeline docs first, and two decisions from me:** what the polling product is
> called, and what the Dashboard becomes on each side. Both block T3. Ask me for those before
> drafting the specs.
>
> Once specs exist, the prompt is:
>
> > Read `docs/features/frontend-domain-split/` and `docs/features/polling-front-door/` —
> > all four docs each — then implement T3 then T5a.
> >
> > T3 splits `frontend/src/api/client.ts` (1,050 lines of hand-rolled useState/useEffect)
> > into two domain modules and gives each product its own nav shell. This absorbs roadmap
> > item #5's TanStack Query migration — do it as part of this, not separately.
> >
> > T5a stands up a second Vercel project and domain for the polling app, pointed at the same
> > Railway API and the same database. No backend split, no second Postgres — those are T4
> > and T5b and they're deliberately deferred until after the election.
> >
> > `news-site` must stay deployable and green at every step.

---

## Deferred until after 2026-11-03

T4 (second Postgres + data migration), T5b (second backend deploy), T6 (cross-cutting
pieces), T7 (repo split). These deliver operational independence, which no visitor can
perceive. A database cutover in late October with live traffic is the one step in this plan
that can take the site down.


---

## Bucket 6 — District poll coverage driven by Wikipedia (roadmap #17)

_Written in Cowork 2026-09-12. Full pipeline docs exist: `docs/features/district-coverage-from-wikipedia/`
(feature plan, acceptance criteria, implementation plan). Test cases are yours to write first._

> Roadmap item #17, slug `district-coverage-from-wikipedia`.
>
> Read all three docs in `docs/features/district-coverage-from-wikipedia/` before writing code.
> `03-implementation-plan.md` names every symbol to change and the order to change them in.
>
> **Your first task is to write `04-test-cases.md`** in that folder, from the approved
> `02-acceptance-criteria.md` (AC-1 through AC-12), following the format of a shipped example
> like `docs/features/ingestion-health/04-test-cases.md`. Map each case to its AC id. Then
> implement. If any criterion can't be turned into a test case, stop and tell Samuel rather
> than reinterpreting it.
>
> **The problem.** `/api/polls/house` has been flat at 112 rows across 37 of 435 districts.
> This is not an ingestion failure — both jobs run and succeed, and `item_count: 0` correctly
> means "no new `poll_id`" because both counters increment only on insert. The Wikipedia stream
> is coverage-capped: `fetch_district_polls` builds its work list from
> `db.query(CompetitiveDistrict).all()`, and that table only ever holds the 60 rows of the
> hardcoded `COMPETITIVE_DISTRICTS` literal, unchanged since `a39fc85` on 2026-06-02.
>
> Measured live across all 50 state pages on 2026-09-12: **86 districts currently have a
> `District N` → `General election` → `Polling` section. The scraper visits 31. 55 are never
> fetched** — IA-1, IA-2, CO-3, NE-1, PA-10, TX-23, VA-1, NY-21, MI-4, CA-40 among them. And
> **29 of the 60 seeded districts have no polling section at all**, so half the seed list is
> dead fetches every six hours.
>
> **The fix** is to stop deciding in advance which districts might have polls. Enumerate them
> from the section list you already fetch per state. Keep `_find_polling_section` working as a
> thin wrapper over the new enumerator so `tests/test_house_polls.py` TC-1 and TC-7 pass
> **unmodified** — that is the regression gate for the refactor, and the implementation plan
> asks you to run it before touching `fetch_district_polls`.
>
> **Fold in the at-large states.** AK, DE, ND, SD, VT and WY 404 with `missingtitle` on every
> run. Verified 2026-09-12: they use the **singular** title
> (`2026_United_States_House_of_Representatives_election_in_Alaska` returns 200), four of the
> six have a general-election `Polling` section today, and they have no `District N` wrapper —
> `General election` sits at toclevel 1 with `Polling` as its child. Store them as district `0`,
> matching `_cand_district` in `polls.py:30-32`. Alaska's page also has a *primary* `Polling`
> section, so the AC-2b guard from PR #8 has to keep holding on at-large pages too.
>
> **Make zero coverage loud.** If zero districts resolve a polling section across all 50 states,
> raise so the scheduler records a `SourceRun` **failure** rather than `success` / `item_count: 0`
> — the pattern that hid the 46-day Economist silence (#10) and the Kalshi incident (#15). A
> partial run still succeeds. Note and accept the consequence: `house_polls_job` covers the
> generic ballot too and they share one `SourceRun` row, so this marks the whole job failed even
> when the generic ballot worked. That is deliberate, and nothing is lost — the generic ballot
> commits before district polls run. Splitting the job into two `SourceRun` ids is out of scope.
>
> No model change, no migration, no frontend change. Do not touch roadmap #12's data-quality
> defects, and do not change `PollCarousel`'s empty-state copy — that is roadmap #21.
>
> Follow `CLAUDE.md`: PR, CI green, merge, then update `docs/ROADMAP.md` #17 to shipped with the
> PR link. Also update `SOURCES.md`'s "House district polls" row, and fix its stale
> "Python runtime is 3.9" line while you are in there.

---

## Bucket 7 — VoteHub district-poll candidate crosswalk (roadmap #18)

_Written in Cowork 2026-09-12. Full pipeline docs exist: `docs/features/votehub-candidate-crosswalk-fix/`.
Independent of Bucket 6 — different service file, different test file, no shared code. Either order._

> Roadmap item #18, slug `votehub-candidate-crosswalk-fix`.
>
> Read all three docs in `docs/features/votehub-candidate-crosswalk-fix/` first.
> `03-implementation-plan.md` states the matching rules precisely — follow them as written.
>
> **Your first task is to write `04-test-cases.md`** from the approved `02-acceptance-criteria.md`
> (AC-1 through AC-13, including AC-2b and AC-4b). The implementation plan already contains a
> table of the name shapes each case needs — use it. Then implement.
>
> **The problem.** Of the 92 `us-representative` polls VoteHub returns, 8 have a null
> `seat_name` and **54 of the remaining 84 are dropped by the crosswalk — only 30 are stored,
> across 17 districts.** Verified by re-implementing the crosswalk against live FEC data on
> 2026-09-12; the simulation reproduced the stored count of 30 exactly.
>
> Root cause: `_normalize_name` sorts the name's tokens and then requires **exact set
> equality**. Token-sorting was added so FEC's `Last, First` would match VoteHub's
> `First Last`, and it does — but it makes any extra, missing or differently-spelled token a
> hard miss. FEC stores legal names with middle names; VoteHub uses ballot names.
>
> **Do not derive a surname by taking the last token of the VoteHub name.** This is AC-2b and
> it is the single biggest bucket: 11 drops have multi-token surnames where the last token is
> only part of the surname — `Monica De La Cruz` (FEC `De La Cruz, Monica`), `Derrick Van Orden`,
> `Marie Gluesenkamp Perez`, `Mariannette Miller-Meeks`, `Marni von Wilpert`. Match by testing
> whether the FEC surname's tokens form a contiguous **suffix** of the VoteHub name's tokens.
> A first draft of this design used the last token and left all 11 unresolved.
>
> **Two constraints from PR #8 that do not move.** AC-11: never read VoteHub's `partisan` field
> — it is the sponsor's lean, not a candidate's party. AC-9: never guess on ambiguity. This
> ticket trades zero-match failures for coverage and must never trade ambiguous-match failures
> for coverage. Say so explicitly in the PR body, because `partisan` sits right there in the
> payload and a reviewer will wonder.
>
> **Expected result, measured:** 30 stored → **67 (+37)**. The 8 residual skips are 4 same-party
> or non-D-vs-R generals that `HousePoll` cannot represent (roadmap #20 — leave alone) and 4
> with no stored candidate match, including `Lupe Castillo` (IL-04, filtered out of our
> `Candidate` table — roadmap #19) and `Janelle Stetson` (PA-10, where VoteHub misspells FEC's
> `Stelson`). If you land materially short of 67, something in the matcher is wrong — say so
> rather than shipping it.
>
> **The 9 generic-label polls stay skipped.** Their answer choices are `"Rep"` / `"Dem"` rather
> than names. Decided 2026-09-12: out of scope for v1, because they are generic-ballot-shaped
> questions rather than named head-to-heads. Give them their own skip cause so they are visibly
> distinct from name-matching failures.
>
> **Add the aggregate skip summary.** Every skip already logs its own WARNING with the unmatched
> names — the evidence was in the logs all along, but nothing counts it, so a 64% drop rate read
> as a healthy run. One `logger.info` summary line per run: returned, bad seat, too few answers,
> inserted, updated, skipped by cause. Keep the per-poll WARNINGs.
>
> **AC-4b needs a committed fixture, not a live call.** The conftest autouse respx guard fails
> any un-mocked HTTP. Capture FEC's filed-candidate list once from
> `GET /v1/candidates/?election_year=2026&office=H` (key is in `backend/.env`), trim it, and
> commit as `tests/fixtures/fec_house_filed_2026.json`. The test asserts no polled district has
> a surname unique among **stored** candidates but ambiguous among **all filed** ones — measured
> at zero occurrences on 2026-09-12. If it ever fails, that is the signal to promote roadmap
> #19, not to loosen AC-4.
>
> No model change, no migration, no frontend change. Do not touch `fetch_votehub_polls`
> (approval + generic ballot) or `compute_average` — #11's `test_staleness_regression.py` pin
> must keep passing.
>
> **One thing to flag rather than auto-merge:** the surname-only fallback is the loosest rule
> here and the largest recovery bucket. Per `CLAUDE.md`'s merge exception, if writing AC-4's
> colliding-pair negative test took any interpretation, say so in the PR and wait.
>
> Otherwise follow `CLAUDE.md`: PR, CI green, merge, then update `docs/ROADMAP.md` #18 to shipped
> with the PR link, and the VoteHub row in `SOURCES.md`.
