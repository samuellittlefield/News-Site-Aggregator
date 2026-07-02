# Acceptance Criteria: Test Harness + CI

**Slug:** `test-harness-ci` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: pytest runs green on a clean checkout
- **Given** a clean checkout with `docker-compose up db` running and dev dependencies installed (`pip install -r requirements.txt -r requirements-dev.txt`)
- **When** `pytest` is run from `backend/`
- **Then** all seed tests are discovered and pass, using a dedicated test database (`newsdb_test`), never `newsdb`

### AC-2: tests make no live network calls
- **Given** the test suite
- **When** any test runs
- **Then** all upstream HTTP calls are mocked (respx); an unmocked request fails the test rather than silently hitting a live API, and neither the scheduler nor the startup refresh fires under TestClient

### AC-3: forecast model determinism
- **Given** a test DB seeded with a minimal, fixed set of model inputs
- **When** `run_model(db, seed=N)` is called twice with the same seed
- **Then** both runs return identical output; a different seed produces different simulation draws

### AC-4: upsert idempotency (kalshi)
- **Given** a mocked Kalshi response fixture with the `CONTROLH`/`CONTROLS` markets
- **When** the kalshi ingestion runs twice against the same test DB
- **Then** the `PredictionMarket` row count is identical after both runs (no duplicates), updated prices from a changed second fixture overwrite the originals, and a market absent from a later fixture is flipped to `active=False` (`MarketSnapshot` intentionally grows one row per market per run and is excluded from the idempotency assertion)

### AC-5: router smoke tests
- **Given** the FastAPI app under TestClient with the test DB
- **When** `GET /health`, `GET /api/forecasts/congress`, and one list endpoint (e.g. `GET /api/trends`) are called
- **Then** each returns 200 with the expected top-level response shape (empty-DB case included — no 500s on empty tables)

### AC-6: CI runs on every PR and push to main
- **Given** the repo on GitHub with `.github/workflows/ci.yml`
- **When** a PR is opened or a commit lands on main
- **Then** two jobs run — backend (pytest against a Postgres service container) and frontend (`npm ci && npm run build`) — and a failure in either marks the check red

### AC-7: CI needs no secrets
- **Given** the CI environment with no `.env` and no repository secrets configured
- **When** the backend job runs
- **Then** the suite passes — no test requires a real `GROQ_API_KEY`, `FEC_API_KEY`, or other live credential

## Data Quality / Edge Cases
- Scheduler gating: `DISABLE_SCHEDULER=1` (or equivalent) must suppress both `start_scheduler()` and the `_startup_refresh()` task in `lifespan` — verify TestClient startup triggers neither.
- Test DB lifecycle: fixtures create the schema per session and roll back per test; two consecutive local runs pass without manual DB cleanup.
- The suite fails fast with a clear message if Postgres is unreachable (rather than hanging).

## Out of Scope
Vitest/frontend unit tests, e2e tests, coverage gates, and backfilling tests across the other 33 services (per feature plan non-goals).

## Sign-off
- [x] Samuel has reviewed and approved these criteria (outline-level sign-off, 2026-07-02).
