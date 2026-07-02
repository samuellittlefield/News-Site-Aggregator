# Feature Plan: Test Harness + CI

**Slug:** `test-harness-ci` &nbsp; **Owner:** Samuel &nbsp; **Status:** Approved — ready for implementation &nbsp; **Date:** 2026-07-02

## Problem / Goal
The backend is ~7,700 lines across 13 routers and 34 services — including a calibrated Monte-Carlo forecast model, FEC pagination with retry logic, and upsert-based ingestion for ~20 tables — and none of it has automated tests. There is no `.github/` directory, so nothing runs on push or PR. Every test-case doc the feature pipeline produces (stage 4) is a manual curl/click-through script that goes stale the moment the code changes. Goal: a pytest harness with a small set of seed tests covering the highest-risk logic, plus a GitHub Actions workflow that runs them (and a frontend type-check/build) on every PR.

## Context
- Cross-cutting — touches no single `SOURCES.md` domain; it's infrastructure under all of them.
- Builds on existing conventions the pipeline already flags as test-worthy: upsert idempotency and scheduler failure isolation.
- Why now: the pipeline templates all carry an "automation note: target `backend/tests/` with pytest once harness exists." This feature makes those notes real. It also unblocks every future feature's stage-4 docs from being manual-only.

## Scope
- [x] New backend test infrastructure: `backend/tests/` with `conftest.py` (test DB fixture, `get_db` override via FastAPI `TestClient`), `backend/requirements-dev.txt` (pytest, pytest-asyncio, respx or equivalent for mocking httpx)
- [x] Seed tests (v1 — deliberately narrow, prove the harness):
  1. **Forecast model determinism** — `run_model(db, seed=...)` returns identical output for identical seed/inputs (`backend/app/services/forecast_model.py`)
  2. **Upsert idempotency** — run one representative ingestion twice against a test DB, assert no duplicate rows (`kalshi.py` is a good candidate: deterministic tickers, simple model)
  3. **Router smoke tests** — `/health`, `/api/forecasts/congress`, and one list endpoint return 200 with expected shape on an empty/seeded DB
- [x] CI: `.github/workflows/ci.yml` — backend job (Postgres service container + pytest), frontend job (`npm ci && npm run build`, which already runs `tsc`)
- [x] Docs: update `SOURCES.md`-adjacent conventions — the pipeline skill and the stage-4 template both say "no test harness yet" and must be updated once this ships

## Non-Goals
- Frontend unit tests (Vitest) — separate follow-up; CI's `tsc + build` catches type breakage for now
- E2E / browser tests (Playwright)
- Backfilling tests across all 34 services — seed tests establish the pattern; coverage grows per-feature via pipeline stage 4
- Coverage thresholds or gates

## Proposed Approach
1. **Test DB**: models use `JSONB` from `sqlalchemy.dialects.postgresql`, so SQLite is out. Tests run against real Postgres — locally the existing `docker-compose.yml` db (a separate `newsdb_test` database), in CI a `postgres:16-alpine` service container. `conftest.py` creates/drops tables per session via `Base.metadata`, wraps each test in a rolled-back transaction.
2. **Fixtures**: a `db` session fixture and a `client` fixture (`TestClient(app)` with `get_db` dependency override). Scheduler startup must not fire in tests — gate `start_scheduler`/`_startup_refresh` behind an env var (e.g. `DISABLE_SCHEDULER=1`) checked in `lifespan`.
3. **Mock upstreams**: seed tests never hit real APIs — mock httpx responses (respx) with recorded JSON samples checked into `backend/tests/fixtures/`.
4. **CI workflow**: two parallel jobs. Backend: checkout → Python setup → `pip install -r requirements.txt -r requirements-dev.txt` → pytest against the service container. Frontend: Node setup → `npm ci` → `npm run build`. Trigger on PR + push to main.
5. **Convention updates**: once merged, the stage-4 template's automation notes flip from "once harness exists" to "add to `backend/tests/`", and the pipeline skill's "no test harness yet" bullet gets removed.

## Open Questions / Risks
- **Python version mismatch (needs a decision)**: `backend/.python-version` says **3.11**, the local venv is **3.9**, and the pipeline skill's convention says "backend runs 3.9." CI has to pin one. Recommendation: pin CI to 3.11 (matches `.python-version` / presumably Railway) and treat the 3.9 constraint as legacy — but confirm what Railway actually runs before choosing.
- `lifespan` currently calls `Base.metadata.create_all` and kicks off the startup refresh; TestClient triggers lifespan by default. The env-var gate must cover both, or tests will make live API calls.
- Interaction with `alembic-migrations` (in-flight sibling feature): if startup switches from `create_all` to `alembic upgrade head`, the test fixture should keep using `Base.metadata.create_all` (fast, always-current) — the two features don't conflict but should land aware of each other.

## References
- Forecast model + backtest prior art: `backend/scripts/backtest.py` (docstring describes the calibration this protects)
- Failure-isolation commit: `fb99f9a` ("Isolate startup refresh steps so one bad source can't starve the rest")
- Pipeline stage-4 template: `docs/features/_template/04-test-cases.md`
