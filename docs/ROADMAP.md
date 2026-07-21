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

## Next

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 3 | Auth on write endpoints (`/api/refresh`, candidate issue-tag POST/PUT) | `write-endpoint-auth` | planned | All 4 pipeline docs drafted 2026-07-21. Scope split during planning: candidate issue-tag POST/PATCH get an `ADMIN_API_KEY` header check; `/api/refresh` stays public (site isn't promoted) but gets an in-memory cooldown instead — Samuel's call |
| 5 | Frontend data layer: replace hand-rolled hooks with TanStack Query | `frontend-data-layer` | idea | `client.ts` is 987 lines of duplicated useState/useEffect |

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
