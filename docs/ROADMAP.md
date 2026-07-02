# News-Site Roadmap

Tracks planned improvements to the Situation Monitor. Each item graduates into the
feature pipeline (`docs/features/<slug>/`) when work starts; status here is the
single place to see where everything stands.

**Statuses:** `idea` → `planned` (pipeline docs in progress) → `in progress` (implementation) → `shipped`

_Last updated: 2026-07-02_

## Now

| # | Item | Slug | Status | Notes |
|---|---|---|---|---|
| 1 | Test harness + CI (pytest, GitHub Actions) | `test-harness-ci` | planned | Docs approved; implement after alembic-migrations. CI pins Python 3.11 (Railway runs 3.11.x) |
| 2 | Adopt Alembic migrations (baseline + deploy hook) | `alembic-migrations` | planned | Docs approved; implement first — includes one-time prod `stamp head` ops step |

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
| "Autogenerate produces empty diff" CI check (model/migration drift) | idea | Deferred from `alembic-migrations`; depends on #1 + #2 |
| `ModelForecast` ingest for Split Ticket (per `SOURCES.md` forecasting sweep) | idea | Blocked on confirming a stable data endpoint |

## Parked

| Item | Slug | Status | Notes |
|---|---|---|---|
| Hacker News trending source | `hacker-news-trending` | draft (dry run) | Full pipeline docs exist; never implemented |

## Shipped

| Item | Slug | Shipped |
|---|---|---|
| Polling page liquid-glass retheme | `polling-page-glass-theme` | PR #4, `26f93ce` (2026-07-02) |
