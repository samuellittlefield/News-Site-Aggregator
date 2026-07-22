# News-Site Roadmap

Tracks planned improvements to the Situation Monitor. Each item graduates into the
feature pipeline (`docs/features/<slug>/`) when work starts; status here is the
single place to see where everything stands.

**Statuses:** `idea` → `planned` (pipeline docs in progress) → `in progress` (implementation) → `shipped`

_Last updated: 2026-07-21_

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
| 5 | Frontend data layer: replace hand-rolled hooks with TanStack Query | `frontend-data-layer` | idea | `client.ts` is 987 lines of duplicated useState/useEffect |
| 8 | Consolidate `/status` + `/admin` into one page | `status-admin-consolidation` | planned | Both pages unlinked + unclear on review 2026-07-21: `/status` has no title/intro, `/admin`'s empty state references a nonexistent `POST /api/admin/run-tagger` endpoint. Design direction (mockup approved): one page, health summary up top, our own data pipelines prominent, third-party status collapsed, AI tag review folded in but de-emphasized (confirmed it gates nothing downstream — no ranked/public list reads `confirmed_issues`). Frontend-only, no new backend actions. All 4 pipeline docs drafted + approved 2026-07-21 — ready for Claude Code |

## Later / chores

| Item | Status | Notes |
|---|---|---|
| Python version cleanup: rebuild local venv on 3.11, drop 3.9 syntax constraint, update pipeline skill | idea | Resolved 2026-07-02: Railway runs 3.11.x; CI pins 3.11. Local venv still 3.9 until rebuilt |
| Add `FEC_API_KEY` to `backend/.env.example` | idea | Key exists in `.env` but not the example — violates repo convention |
| Add a README | idea | No README at repo root |
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
