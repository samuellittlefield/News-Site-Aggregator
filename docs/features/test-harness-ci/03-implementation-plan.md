# Implementation Plan: Test Harness + CI

**Slug:** `test-harness-ci` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Add pytest infrastructure under `backend/tests/` with a Postgres-backed test DB, mocked upstreams, and a scheduler gate; three seed test modules prove the pattern; a GitHub Actions workflow runs backend tests and the frontend build on every PR.

## Backend Changes
*(Python 3.9-compatible syntax — but see Risks: CI pins 3.11 per `.python-version`)*

| File | Change |
|---|---|
| `backend/requirements-dev.txt` | new — `pytest`, `pytest-asyncio`, `respx` (pin versions compatible with `httpx==0.27.2`) |
| `backend/pytest.ini` | new — `testpaths = tests`, asyncio mode auto, env defaults (`DISABLE_SCHEDULER=1`, `TEST_DATABASE_URL` fallback) |
| `backend/app/main.py` | gate scheduler in `lifespan`: skip `start_scheduler()` and `_startup_refresh()` when `os.getenv("DISABLE_SCHEDULER") == "1"` |
| `backend/tests/__init__.py` | new — empty |
| `backend/tests/conftest.py` | new — session-scoped engine on `TEST_DATABASE_URL` (default `postgresql://newsuser:newspass@localhost:5432/newsdb_test`; auto-create the DB if missing), `Base.metadata.create_all` once per session, per-test transactional `db` fixture with rollback, `client` fixture (`TestClient(app)` with `get_db` override), autouse respx guard so unmocked HTTP raises |
| `backend/tests/fixtures/kalshi_markets.json` | new — recorded Kalshi response with `CONTROLH-2026-*`/`CONTROLS-2026-*` markets; per `kalshi.py`: `volume_24h_fp` must be a numeric string ≥ 1000 (else filtered), prices are decimal dollar strings. Variants: changed-prices (update assertion) and one-market-removed (deactivation assertion) |
| `backend/tests/test_forecast_model.py` | new — AC-3: seed minimal inputs, assert `run_model(db, seed=42)` twice → identical dicts; `seed=43` → differs |
| `backend/tests/test_kalshi_upsert.py` | new — AC-4: respx-mock Kalshi, run ingestion twice, assert stable row count + price update on second fixture |
| `backend/tests/test_routers_smoke.py` | new — AC-5: `/health`, `/api/forecasts/congress`, `/api/trends` return 200 with expected shape on empty DB |

No upstream APIs are called (everything mocked) — no rate-limit or isolation concerns.

## Frontend Changes
| File | Change |
|---|---|
| — | none; CI reuses existing `npm run build` (`tsc && vite build`) as the type-check gate |

## CI
| File | Change |
|---|---|
| `.github/workflows/ci.yml` | new — trigger `pull_request` + `push: [main]`. Job `backend`: `postgres:16-alpine` service, Python setup (pin per `.python-version`), install reqs, `pytest` from `backend/`. Job `frontend`: Node 20, `npm ci`, `npm run build` from `frontend/` |

## Data Model / Migration Notes
None — no schema changes. Test fixtures use `Base.metadata.create_all` directly (deliberately independent of the `alembic-migrations` feature).

## Sequencing
1. Scheduler gate in `main.py` (smallest change, unblocks everything)
2. `requirements-dev.txt` + `pytest.ini` + `conftest.py` — get an empty suite running against the test DB
3. Router smoke tests (no fixtures needed) → forecast model test → kalshi upsert test (needs recorded fixture)
4. CI workflow; verify on a draft PR with an intentionally failing test, then fix
5. Docs updates (below)

## Documentation Updates
- [ ] `.env.example`: add `TEST_DATABASE_URL` (commented, with default)
- [ ] `docs/features/_template/04-test-cases.md`: flip automation notes from "once harness exists" to "add to `backend/tests/`"
- [ ] `docs/ROADMAP.md`: status → in progress / shipped
- [ ] Pipeline skill: the "no test harness yet" convention is now stale — Samuel updates the skill (not editable from the repo)
- [ ] `SOURCES.md`: no change (no source touched)

## Risks / Rollback
- **Python version**: CI must pin one version. Recommendation: 3.11 (matches `backend/.python-version` and presumably Railway). If Railway turns out to run 3.9, change one line in the workflow. Code stays 3.9-compatible either way for now.
- **Lifespan gate misses a path** → tests hit live APIs. Mitigated by the autouse respx guard (AC-2): any unmocked request raises loudly.
- **Rollback**: delete `.github/workflows/ci.yml` and `backend/tests/`; the scheduler gate is inert when the env var is unset.

## Test Plan Pointer
See `04-test-cases.md` for the cases this implementation must satisfy.
