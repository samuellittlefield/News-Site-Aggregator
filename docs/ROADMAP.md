# News-Site Roadmap

Tracks planned improvements to the Situation Monitor. Each item graduates into the
feature pipeline (`docs/features/<slug>/`) when work starts; status here is the
single place to see where everything stands.

**Statuses:** `idea` → `planned` (pipeline docs in progress) → `in progress` (implementation) → `shipped`

_Last updated: 2026-09-11_

## Now

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 1 | Test harness + CI (pytest, GitHub Actions) | `test-harness-ci` | shipped | `backend/tests/` (Postgres `newsdb_test`, respx-mocked upstreams, scheduler gated via `DISABLE_SCHEDULER=1`); 8 seed tests green. `.github/workflows/ci.yml` runs backend pytest + frontend build on PR/push. CI pins Python 3.11 (Railway runs 3.11.x). TC-7/TC-8 (red-check verification) to confirm on first PR |
| 2 | Adopt Alembic migrations (baseline + deploy hook) | `alembic-migrations` | shipped | Baseline `1cfc95e31a13` = prod (drift reconciled via Plan A into models); prod `stamp head` done 2026-07-07; Procfile runs `upgrade head`. `create_all` kept as release-1 safety net (remove in follow-up) |
| 6 | Fix district poll scraper + add VoteHub as a second district-polling source | `district-poll-scraper-fix` | shipped | PR [#8](https://github.com/samuellittlefield/News-Site-Aggregator/pull/8). v1: `house_polls.py` now fetches each state's consolidated page and resolves `District N → General election → Polling` via the section tree, keying tables off candidate-name `(R)`/`(D)`/`(I)` suffixes; primary-vs-general collision guarded (AC-2b), failures logged not silent (AC-4). v2: `votehub.py` queries `poll_type=us-representative` and upserts into `HousePoll` via a `Candidate`-table name→party crosswalk (never VoteHub's `partisan` field, AC-11; unmatched/ambiguous skipped+logged, AC-9). Additive `HousePoll.source` column (`wikipedia`\|`votehub`), migration `b2f1a7c4d9e3`. Tests `test_house_polls.py` + `test_votehub_house_polls.py` (TC-1…TC-11); full suite 22 passed |
| 4 | Per-source ingestion health tracking (`SourceRun` table → StatusPage) | `ingestion-health` | shipped | PR [#9](https://github.com/samuellittlefield/News-Site-Aggregator/pull/9). Upserted `SourceRun` row per registered scheduler job (status, last run/success time, item count, last error, cadence), recorded from all 17 `refresh_*` functions inside the existing try/except so failure isolation is unchanged, with recording itself defensively wrapped (AC-3). `refresh_faa` got a short-lived session; `refresh_breakout` excluded (not scheduled). `SOURCE_CADENCE` is the single source of truth shared by the scheduler and the new `GET /api/status/sources` route; TC-7 diffs registered job ids against it to catch drift. New "Data Sources" panel on StatusPage flags failing/stale sources + shows last error. Migration `c3d2e5f6a7b8`; tests `test_source_run.py` + `test_status_sources.py` (TC-1…TC-7), full suite 30 passed. Startup-refresh concurrency deferred as a non-goal/follow-up |
| 7 | Fix in-house forecast model's silent swing fallback | `forecast-model-swing-fallback-fix` | shipped | PR [#11](https://github.com/samuellittlefield/News-Site-Aggregator/pull/11). Bug found live 2026-07-21: House model showed 36% Dem vs. Kalshi's 83% Dem — `swing_d: 0` exactly, meaning `_current_env()` hit its hardcoded-2024-baseline fallback with zero live polling signal, silently. Added `GenericBallotAggregate` table, persisted from the Wikipedia aggregator rows `refresh_house_polls` already fetches every 6h (previously discarded), isolated in its own try/except (TC-9). `_current_env()` is now a 3-tier fallback (VoteHub live average → persisted aggregator mean → static 2024 baseline), returning a `swing_source` tag (`votehub`\|`aggregator`\|`fallback`) threaded through `run_model()`, `ChamberModel`, and the model card, which shows a warning only on the fallback tier (AC-5). `_kalshi_source`/`_polymarket_source` and `/api/polls/generic-ballot` untouched (AC-6, TC-10). Migration `d4e5f6a7b8c9`; tests `test_forecast_swing_source.py` + `test_generic_ballot_persistence.py` (TC-1…TC-5, TC-7…TC-10), full suite 54 passed |

## Next

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 3 | Auth on write endpoints (`/api/refresh`, candidate issue-tag POST/PUT) | `write-endpoint-auth` | shipped | PR [#10](https://github.com/samuellittlefield/News-Site-Aggregator/pull/10). `require_admin_key` (`auth.py`) gates the two candidate issue-tag routes via `X-Admin-Key` vs. `ADMIN_API_KEY` (read at call time, `secrets.compare_digest`, fails closed if unset); `/api/refresh` stays public (called from the public `TrendsPage` button) with a 60s in-memory cooldown instead (429 on repeats). Frontend `AdminPage`/`client.ts` prompt for the key once per session (memory only, never persisted), attach it to confirm/reject/add-tag calls, and re-prompt with a visible error banner on 401. Tests `test_write_endpoint_auth.py` (TC-1–TC-7, TC-10); full suite 43 passed. Browser-verified end to end |
| 5 | Frontend data layer: replace hand-rolled hooks with TanStack Query | `frontend-data-layer` | idea | `client.ts` is 987 lines of duplicated useState/useEffect. Likely folds into `extract-elections-app` ticket 3 rather than shipping separately |
| 9 | Extract elections/polling into a standalone project (gradual, multi-ticket) | `extract-elections-app` | planned | Feature plan `docs/features/extract-elections-app/01-feature-plan.md` (2026-07-23). Backend has no cross-domain imports (re-confirmed 2026-09-11: `routers/` and `services/` still flat, scheduler still 17 ungrouped `refresh_*` jobs, `client.ts` still 1,050 lines with no TanStack Query — **0 of 7 tickets implemented**). Re-sequenced 2026-09-11 against the 3 Nov election, split by whether a visitor can perceive the difference — see the Extraction tickets section below. Open questions narrowed from five to two for near-term work: naming, and what the Dashboard becomes on each side. Repo strategy, Astronomy's home, and shared-vs-duplicated health tracking all sit in the deferred half |
| 8 | Consolidate `/status` + `/admin` into one page | `status-admin-consolidation` | shipped | PR [#12](https://github.com/samuellittlefield/News-Site-Aggregator/pull/12). `AdminPage` is now the consolidated page: title + read-only intro, a summary banner reusing `SourceHealthSection`'s newly-exported `classify()`/`summarizeSourceHealth()` (AC-3, no divergent calculation), `SourceHealthSection` prominent near the top, `ServiceStatusSection` collapsed behind a native `<details>` by default (no new dependency). Default admin tab flipped `"pending"` → `"candidates"` so candidate browsing leads over tag review. Dead `POST /api/admin/run-tagger` empty-state line removed, replaced with accurate weekly-scheduled-job copy. `StatusPage.tsx` deleted; `/status` redirects client-side to `/admin` via `useNavigation.ts`'s `fromPath` (URL bar normalized via `history.replaceState`) — also caught and fixed one hardcoded internal link (`DashboardPage`'s `StatusPanel` → `navigate("status")`) that would've dangled otherwise. Frontend-only, no backend changes. All 12 cases in `04-test-cases.md` browser-verified manually (no Vitest harness yet); TC-10's network check confirmed only the 5 expected endpoints fire, no new/duplicate calls beyond pre-existing `React.StrictMode` dev-only doubling |

## Extraction tickets (item #9)

Sequenced 2026-09-11. The seven tickets divide by whether a visitor can tell the difference:
tickets 1-3 plus the frontend half of 5 are the entire perceptible product and never touch
the database; the rest deliver operational independence that is invisible from outside.

**Go/no-go: 2026-10-13.** If T1-T3 aren't merged by then, ship T5a's nav shell and domain on
the existing unsplit build instead. The failure mode to avoid is being half-migrated on
election night.

| Ticket | Item | Slug | Status | Target |
|---|---|---|---|---|
| T1 | Draw the backend seam — regroup `routers/` + `services/` into two bounded packages, no behaviour change | `elections-seam` | planned | before election |
| T2 | Split the scheduler into two independently-disableable job groups (still one process) | `scheduler-split` | planned | before election |
| T3 | Split `client.ts` into two domain modules + two nav shells, absorbing item #5's TanStack Query migration | `frontend-domain-split` | planned | before election |
| T5a | Second Vercel project + domain for the polling app, same API and database | `polling-front-door` | planned | before election |
| T4 | Second Postgres + fresh Alembic history, migrate elections tables and data | `elections-database` | idea | after election |
| T5b | Second backend deploy target for the extracted API | `elections-backend-deploy` | idea | after election |
| T6 | Resolve cross-cutting pieces: `SourceRun`/`ServiceStatus`, Astronomy, Dashboard on each side | `extraction-cross-cutting` | idea | after election |
| T7 | Physical repo split + CI/`CLAUDE.md`/`SOURCES.md` updates on both sides | `extraction-repo-split` | idea | after election |

## Polling data fixes (Sept 2026 audit)

Found 2026-09-11 auditing production ahead of the extraction. **Every one of these jobs
reports `status: success`** — none surfaced on the Data Sources panel. Freshness was measured
by poll fieldwork end date, not job execution time; job health only answers "did the scheduler
fire".

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 10 | Fix Economist/YouGov report discovery | `economist-discovery-fix` | planned | **Blocker.** Latest stored report is fieldwork 2026-07-25/27, fetched 2026-08-02 — 46 days stale. The 12h job runs and records `success` with `item_count: 0`. Provably ours, not upstream: VoteHub carries a YouGov/Economist generic-ballot poll fielded 2026-09-04/08 whose source URL is `econTabReport_SlcWdVd.pdf`, same CloudFront host `economist_yougov.py` discovers via Wikipedia. Reports are being published; discovery stopped finding them. Same failure shape as PR #8. Feeds `ApprovalSection` + crosstabs on the Polls tab |
| 11 | Staleness labelling on poll cards | `poll-staleness-labels` | idea | VoteHub's approval stream is 14 days stale **upstream** — verified against `api.votehub.com/polls?poll_type=approval`: 2,945 rows, newest end_date 2026-08-28, while their generic-ballot stream was current to 09-08. Not fixable in `votehub.py`. The approval average is built from 5 polls in a 21-day window and shown with no indication of age. Options: visible "fieldwork through X" label, a second approval source, or hide the card past a staleness threshold |
| 12 | District poll data quality cleanup | `district-poll-data-quality` | idea | Wikipedia stream (`house_polls.py`): 3 rows dated in the future (end_date 2026-09-28, seen 09-11); 82 of 112 rows null on `start_date`/`source_url`/`sample_size`; markup bleeding into the pollster field (`Emerson Collegename=NPI`, truncated footnote text ending mid-word); pollster-name variants defeating dedup (`SurveyUSA` vs `Survey USA` — 9 duplicate groups / 20 rows). Coverage 37 of 435 districts. All cosmetically visible on the district map and carousel |
| 13 | `SourceRun` staleness detection | `sourcerun-staleness` | idea | `status: success` + `item_count: 0` is indistinguishable from broken — three polling jobs show it, only one is actually broken. Structurally the same bug as the 2026-07-21 forecast swing fallback, one layer up: PR #11 taught the *model* to report which tier it landed on, the *ingestion* layer never learned it. `SourceRun` already stores `cadence_minutes`; add an expected-freshness threshold per source and make "ran clean, produced nothing new for N cycles" a distinct state from success |

## Later / chores

| Item | Status | Notes |
|---|---|---|
| Python version cleanup: rebuild local venv on 3.11, drop 3.9 syntax constraint, update pipeline skill | idea (overdue) | Resolved 2026-07-02: Railway runs 3.11.x; CI pins 3.11. Local venv still 3.9 until rebuilt |
| Add `FEC_API_KEY` to `backend/.env.example` | idea | Key exists in `.env` but not the example — violates repo convention |
| Add a README | idea | No README at repo root |
| Update `news-site-feature-pipeline` skill — conventions are stale | idea | Skill still says "no test harness yet" (pytest + CI shipped, PR #7) and "backend runs 3.9" (Railway + CI are 3.11), and has no Alembic migration checklist. Update via Settings > Capabilities |
| Vitest / frontend unit tests | idea | Deferred from `test-harness-ci` non-goals |
| "Autogenerate produces empty diff" CI check (model/migration drift) | idea (unblocked) | Deferred from `alembic-migrations`; #1 + #2 both shipped, so this is now buildable in `backend/tests/` + `ci.yml` |
| `ModelForecast` ingest for Split Ticket (per `SOURCES.md` forecasting sweep) | idea | Blocked on confirming a stable data endpoint |

## Parked

| Item | Slug | Status | Notes |
|---|---|---|---|
| Hacker News trending source | `hacker-news-trending` | draft (dry run) | Full pipeline docs exist; never implemented |

## Shipped

| Item | Slug | Shipped |
|---|---|---|
| Polling page liquid-glass retheme | `polling-page-glass-theme` | PR #4, `26f93ce` (2026-07-02) |
