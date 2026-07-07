# Implementation Plan: District Poll Scraper Fix + VoteHub District Backbone

**Slug:** `district-poll-scraper-fix` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary

Two independent backend changes landing together:

1. **v1 (Wikipedia fix):** rewrite district-poll discovery in `house_polls.py` to fetch each
   state's consolidated 2026 House elections page, locate each competitive district's
   `District N → General election → Polling` subsection by walking the page's section tree
   (careful to skip a same-named `Polling` subsection under a primary section instead — AC-2b),
   and parse that subsection's wikitable using candidate-name/party-suffix header matching.
2. **v2 (VoteHub backbone):** extend `votehub.py` to also query `poll_type=us-representative`,
   resolve each poll's candidate names to a party via the existing `Candidate` table, and
   upsert into `HousePoll` alongside the Wikipedia-sourced rows.

Router and scheduler are unchanged for both — same `/api/polls/house*` routes, same
`house_polls_job` (6h) and `votehub_job` (hourly) cadences. One small, additive model change:
a `source` column on `HousePoll` (see Data Model / Migration Notes).

## Backend Changes
*(this repo runs Python 3.11 now — the `.python-version` file and CI both confirm it; `X | Y`
union syntax is fine, `Optional[...]` is no longer required. Flagging since the pipeline
skill's cached guidance still says 3.9/`Optional`-only — see note to Samuel about updating it.)*

| File | Change |
|---|---|
| `backend/app/services/house_polls.py` | Replace `_wiki_page_for_district()` with `_state_wiki_page(state) -> str` (state name → `2026_United_States_House_of_Representatives_elections_in_<State>`). Add `_fetch_state_sections(client, state) -> list[dict]` (calls `action=parse&prop=sections`, returns the section list or `[]` + logs a warning on non-200/`error` body). Add `_find_polling_section(sections, district) -> Optional[int]` (walks `toclevel`s: finds `District {district}` at toclevel 1, then within that district's range finds `General election` at toclevel 2, then scans **only its descendants** — entries after the `General election` line and before the next toclevel ≤2 line — for a `Polling` heading. Returns `None` — not an error — if no `Polling` subsection exists yet. Critically, this must NOT match a `Polling` heading nested under `Republican primary`/`Democratic primary` instead: spot-checked live on 2026-07-07, NY-17 and NE-2 both have a primary-level `Polling` section (primary horse-race polls) and no general-election one yet — a naive "first Polling heading under the district" search would grab the wrong table and mislabel primary polls as general-election dem/rep numbers; see AC-2b). Add `_fetch_section_wikitext(client, page, section_idx) -> str` (fetches just that section's wikitext by index; logs a warning on failure). Replace `_extract_polls_from_wikitext()` with `_extract_polls_from_polling_section(wikitext, state, district) -> list[dict]`, keying header cells by trailing `(R)`/`(D)`/`(I)` after stripping `<br/>`/wiki markup, rather than substring-matching "democrat"/"republican". Rewrite `fetch_district_polls(db)` to group `COMPETITIVE_DISTRICTS` by state, fetch each state's sections once, then loop its districts — each state wrapped in its own try/except so one state's failure doesn't stop the rest (AC-5) |
| `backend/app/services/votehub.py` | Add `"us-representative": {"poll_type": "us-representative"}` to `POLL_QUERIES`. Add `_district_candidates(db, state, district) -> dict[str, str]` — queries `Candidate` (`office="H"`, matching state/district) and builds a normalized-name→party map (lowercase, strip punctuation and common suffixes `jr.`/`sr.`/`ii`/`iii`/`iv`). Add `_match_candidate_party(name, crosswalk) -> Optional[str]` — normalizes the VoteHub `answers[].choice` name and looks it up; returns `None` (not a guess) on zero or multiple matches. Add a new branch in `fetch_votehub_polls(db)` (or a sibling `fetch_votehub_house_polls(db)` called from the same job) that: for each `us-representative` poll, parses `seat_name` → `(state, district)`, builds/reuses the crosswalk, resolves `dem`/`rep` via matched candidates, and upserts into `HousePoll` with `source="votehub"`, `poll_id=f"votehub-{p['id']}"`. Skips (and logs, per AC-9) polls where either candidate's party can't be resolved. Never reads the poll's own `partisan` field for this (AC-11) — that field stays reserved for the existing approval/generic-ballot use, if any |
| `backend/app/models.py` | Add `source = Column(String(16), nullable=False, server_default="wikipedia")` to `HousePoll` — small additive column, existing rows default to `"wikipedia"` (accurate, since VoteHub ingestion didn't exist before this) |
| `backend/alembic/versions/` | New migration: add `HousePoll.source` column with the server-side default above (safe on existing rows, no backfill script needed) |
| `backend/app/routers/polls.py` | No route changes; `HousePollOut` response model gains `source: str` so the frontend *can* distinguish streams later if wanted — optional, cheap to include now |
| `backend/app/scheduler.py` | No change — v1 rides the existing `house_polls_job` (6h), v2 rides the existing `votehub_job` (hourly, so VoteHub-sourced district polls actually refresh faster than Wikipedia-sourced ones) |

Failure isolation: today's per-district try/except becomes per-state try/except for v1 (fewer,
coarser units, since one state-sections fetch now covers all of that state's competitive
districts). Within a state, a single district's missing `Polling` section (AC-7) is a normal
`continue`, not an exception — only network/parse failures on the *state* fetch itself get
caught and logged as warnings (AC-4). For v2, failure isolation is per-poll: one poll with an
unresolvable candidate name is skipped+logged (AC-9); it doesn't stop processing the rest of
VoteHub's `us-representative` polls, and a VoteHub-wide failure (network, non-200) is caught the
same way the existing `approval`/`generic-ballot` loop already catches per-`poll_type` failures.

## Frontend Changes

None. The Polls tab's district map/carousel already reads from `HousePoll` via existing routes
— it starts showing real data once ingestion actually populates rows; no component changes
needed.

## Data Model / Migration Notes

One small additive migration: `HousePoll.source` (`String(16)`, `NOT NULL`, server default
`"wikipedia"`). Safe on existing rows (there shouldn't be any real ones yet, given the bug, but
the default makes it safe regardless). `poll_id` stays the existing upsert key for Wikipedia
rows (`hashlib.md5(f"{state}{district}{pollster}{dates}{dem_val}{rep_val}")`-derived); VoteHub
rows use `f"votehub-{votehub_id}"` as their own stable, collision-free key — so re-runs against
unchanged upstream data remain a no-op for both streams independently (AC-6, AC-10).

## Sequencing

1. **v1 first:** add the new Wikipedia helper functions (`_state_wiki_page`,
   `_fetch_state_sections`, `_find_polling_section`, `_fetch_section_wikitext`,
   `_extract_polls_from_polling_section`) alongside the existing code in `house_polls.py`
   without wiring them in yet.
2. Rewrite `fetch_district_polls(db)` to use the new state-grouped flow; remove
   `_wiki_page_for_district()` and the old `_extract_polls_from_wikitext()` once the new path
   is wired and passing tests.
3. Add `backend/tests/test_house_polls.py` (see `04-test-cases.md`) with respx-mocked
   `action=parse&prop=sections` and `action=parse&prop=wikitext&section=N` responses, using
   trimmed real fixtures (PA-8, NY-17, NE-2 section lists, per the live verification in the
   feature plan).
4. **Then the migration:** add the `HousePoll.source` column (Alembic revision) — do this
   before wiring v2 so `votehub.py` can rely on the column existing.
5. **v2:** extend `votehub.py` per the Backend Changes row above; add
   `backend/tests/test_votehub_house_polls.py` (see `04-test-cases.md`) with a respx-mocked
   `us-representative` fixture and a seeded `Candidate` crosswalk.
6. Update the `SOURCES.md` "House district polls" row to mention the state-page/section-based
   discovery mechanism, and note that `votehub.py` now also feeds `HousePoll` via
   `us-representative` polls (cross-reference both rows so the doc doesn't imply two unrelated
   pipelines).
7. Manual smoke check against production data shape isn't possible from Cowork (no live DB
   access here per the Cowork/Claude Code SDLC split) — Claude Code should run the new pytest
   cases plus a one-off local `refresh_house_polls()` + `fetch_votehub_polls()` call against a
   dev DB before merge.

## Documentation Updates
- [x] `SOURCES.md` — update "House district polls" row (state-page mechanism) and "VoteHub
  polls" row (now also feeds `HousePoll`, not just approval/generic-ballot)
- [ ] `.env.example` — not needed, no new env vars/secrets

## Risks / Rollback

- Wikipedia section numbering is not stable across edits — sections must be re-resolved by
  title lookup on every run (already the plan), never cached by index across runs.
- If Wikipedia's table structure varies more than the PA-8/NY-17/NE-2 sample suggests (e.g. a
  state using a different subsection name than "Polling", or nesting one level differently),
  some districts could still silently return 0 polls — mitigated by AC-4's logging making that
  visible immediately instead of months later.
- Confirmed the primary-vs-general Polling collision (AC-2b) is not rare — 2 of the 3 states
  spot-checked have it. Also confirmed page structure varies in unrelated ways (Nebraska nests
  an extra "Candidates" toclevel between the primary heading and its Nominee/Withdrawn/Declined
  children) — a reminder that section-tree walking must key off heading *names* at each level,
  not fixed toclevel depth or fixed child counts.
- Rollback (v1): same-file change plus one additive column — revert the `house_polls.py`
  commit and redeploy; no data cleanup needed since old runs never wrote rows (nothing to
  undo). The `source` column migration can stay even if v1's logic is reverted (it's harmless
  and additive).
- Rollback (v2): revert the `votehub.py` change; existing `approval`/`generic-ballot` ingestion
  is untouched and unaffected. If candidate-name matching turns out too unreliable in practice,
  this can be disabled independently of v1 without reverting the Wikipedia fix.
- Scheduler job IDs/cadences unchanged, so no Procfile/deploy config changes and no risk to
  other jobs.
- v2-specific risk: if `fec_candidates.py`'s refresh (24h cadence) runs stale relative to
  VoteHub's hourly polls, the crosswalk could briefly miss a very recently filed candidate —
  self-correcting on the next `Candidate` refresh, not a persistent failure.

## Test Plan Pointer
See `04-test-cases.md` for the cases this implementation must satisfy.
