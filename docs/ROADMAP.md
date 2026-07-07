# News-Site Roadmap

Tracks planned improvements to the Situation Monitor. Each item graduates into the
feature pipeline (`docs/features/<slug>/`) when work starts; status here is the
single place to see where everything stands.

**Statuses:** `idea` → `planned` (pipeline docs in progress) → `in progress` (implementation) → `shipped`

_Last updated: 2026-07-07_

## Now

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 1 | Test harness + CI (pytest, GitHub Actions) | `test-harness-ci` | shipped | `backend/tests/` (Postgres `newsdb_test`, respx-mocked upstreams, scheduler gated via `DISABLE_SCHEDULER=1`); 8 seed tests green. `.github/workflows/ci.yml` runs backend pytest + frontend build on PR/push. CI pins Python 3.11 (Railway runs 3.11.x). TC-7/TC-8 (red-check verification) to confirm on first PR |
| 2 | Adopt Alembic migrations (baseline + deploy hook) | `alembic-migrations` | shipped | Baseline `1cfc95e31a13` = prod (drift reconciled via Plan A into models); prod `stamp head` done 2026-07-07; Procfile runs `upgrade head`. `create_all` kept as release-1 safety net (remove in follow-up) |
| 6 | Fix district poll scraper + add VoteHub as a second district-polling source | `district-poll-scraper-fix` | in progress | v1: `house_polls.py` targets per-district Wikipedia pages that don't exist for this cycle (consolidated to state-level pages with `District N → General election → Polling` subsections, HTTP 200 on missing pages masked the failure); real polls exist (e.g. 3 for PA-8) and were never ingested. Spot-checked NY-17 + NE-2, found a primary-vs-general Polling collision risk (AC-2b). v2: VoteHub's already-integrated API has an unused `poll_type=us-representative` category (51 polls / ~19 districts, structured JSON, `seat_name` field) — more reliable than Wikipedia scraping; added as a second stream via a candidate-name→party crosswalk against the existing `Candidate` table, plus a small additive `HousePoll.source` column/migration. Full pipeline (all 4 docs) approved by Samuel 2026-07-07, handed to Claude Code |

## Next

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 3 | Auth on write endpoints (`/api/refresh`, candidate issue-tag POST/PUT) | `write-endpoint-auth` | idea | Simple API-key header dependency; small |
| 4 | Per-source ingestion health tracking (`SourceRun` table → StatusPage) | `ingestion-health` | idea | Also: make startup refresh concurrent |
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
