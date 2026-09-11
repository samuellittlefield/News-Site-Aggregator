# Claude Code kickoff prompts

Written in Cowork 2026-09-11 after auditing production. Paste one bucket at a time into
Code mode. They're ordered — buckets 1–3 are the data fixes, 4–5 are the extraction.

**Spec status:** buckets 1–3 are bug fixes whose findings are specific enough to act as the
spec, and each prompt carries the evidence inline. Buckets 4–5 are architectural and should
get the four pipeline docs written in Cowork first — their prompts say so.

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

> **Needs pipeline docs first.** These are roadmap tickets T1 (`elections-seam`) and T2
> (`scheduler-split`) under item #9, and per `CLAUDE.md` the four docs should land in
> `docs/features/<slug>/` before implementation. Ask me to write them in Cowork first.
>
> Once specs exist, the prompt is:
>
> > Read `docs/features/elections-seam/` and `docs/features/scheduler-split/` — all four docs
> > each — then implement both, seam first.
> >
> > T1 regroups `backend/app/routers/` and `backend/app/services/` into two bounded packages
> > (elections/polling vs. news/trends/weather/hazards) with no behaviour change. The July
> > feature plan confirmed there are no cross-domain imports, and I re-confirmed it on
> > 2026-09-11 — this should be a move, not a rewrite. If you find a cross-domain import,
> > stop and tell me; that changes the plan.
> >
> > T2 splits the 17 `refresh_*` jobs in `scheduler.py` into two independently-disableable
> > groups, still in one process. Failure isolation must be unchanged — one bad upstream
> > still can't starve the others.
> >
> > The full test suite passing unchanged is the acceptance bar for both. Neither ticket
> > touches the database.

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
