# Test Cases: Test Harness + CI

**Slug:** `test-harness-ci` &nbsp; **Source:** `02-acceptance-criteria.md`

Meta-note: the deliverable here *is* the automated suite, so most cases below are manual verifications that the harness itself behaves — run once at implementation time and again at PR review.

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2, TC-3 |
| AC-3 | TC-4 |
| AC-4 | TC-5 |
| AC-5 | TC-6 |
| AC-6 | TC-7, TC-8 |
| AC-7 | TC-9 |

## Backend

### TC-1 — clean-checkout run (covers AC-1)
- **Type:** manual (harness verification)
- **Setup:** fresh clone, `docker-compose up -d db`, new venv, `pip install -r requirements.txt -r requirements-dev.txt`
- **Steps:**
  1. From `backend/`, run `pytest -v`
  2. Run `pytest -v` a second time without touching the DB
- **Expected Result:** all tests pass both times; `psql` shows a `newsdb_test` database was used; `newsdb` untouched
- **Automation note:** self-automating — this *is* the suite

### TC-2 — no scheduler under TestClient (covers AC-2)
- **Type:** integration (in-suite assertion)
- **Setup:** `client` fixture from `conftest.py`
- **Steps:** instantiate TestClient; inspect logs/APScheduler state
- **Expected Result:** no "Scheduler started" log line, no startup-refresh log lines, no APScheduler jobs registered
- **Automation note:** write as an actual test in `backend/tests/test_routers_smoke.py` (assert `scheduler.running is False`)

### TC-3 — unmocked HTTP request fails loudly (covers AC-2)
- **Type:** manual (harness verification)
- **Setup:** temporarily add a test that calls `httpx.get("https://example.com")` with no respx mock
- **Steps:** run `pytest` on that test
- **Expected Result:** the test errors with a "call not mocked" failure — it does not reach the live network. Remove the temp test after verifying.
- **Automation note:** the autouse respx guard covers this permanently

### TC-4 — forecast model determinism (covers AC-3)
- **Type:** unit (`backend/tests/test_forecast_model.py`)
- **Setup:** `db` fixture seeded with minimal model inputs (a handful of district priors; no FEC rows)
- **Steps:** call `run_model(db, seed=42)` twice, then `run_model(db, seed=43)`
- **Expected Result:** run 1 == run 2 (full output dict); run 3 differs in simulation-derived fields
- **Automation note:** in suite

### TC-5 — kalshi upsert idempotency (covers AC-4)
- **Type:** integration (`backend/tests/test_kalshi_upsert.py`)
- **Setup:** respx mock on `external-api.kalshi.com/trade-api/v2/markets` returning `fixtures/kalshi_markets.json`. Upsert key is `(platform="kalshi", market_id=<ticker>)`; fixture markets need `volume_24h_fp` ≥ 1000 (as a string — Kalshi sends numeric strings) or they're filtered out, and prices come from `last_price_dollars` / `yes_bid_dollars` / `yes_ask_dollars` (decimal dollar strings, not cents)
- **Steps:**
  1. Run `fetch_kalshi(db)`; record `PredictionMarket` row count
  2. Run again with the identical fixture → `PredictionMarket` count unchanged (note: `MarketSnapshot` grows by one row per market per run — that's by design, don't assert on total table size)
  3. Run with the changed-prices variant → `PredictionMarket` count unchanged, `yes_price` values updated
  4. Run with one market removed from the fixture → that row flips to `active=False` (retirement sweep)
- **Expected Result:** as per steps — no duplicate markets, updates overwrite, absent markets deactivate
- **Automation note:** in suite

### TC-6 — router smoke (covers AC-5)
- **Type:** integration (`backend/tests/test_routers_smoke.py`)
- **Setup:** `client` fixture, empty test DB
- **Steps:** `GET /health`, `GET /api/forecasts/congress`, `GET /api/trends`
- **Expected Result:** all 200; response shapes match; no 500s on empty tables
- **Automation note:** in suite

## CI

### TC-7 — red check on failing test (covers AC-6)
- **Type:** manual (CI verification)
- **Setup:** draft PR containing `assert False` in a new test
- **Steps:** open the PR, wait for checks
- **Expected Result:** backend job fails, PR check is red; after removing the bad test, checks go green
- **Automation note:** one-time verification at rollout

### TC-8 — frontend build gate (covers AC-6)
- **Type:** manual (CI verification)
- **Setup:** draft PR introducing a deliberate TS type error in any component
- **Steps:** open the PR, wait for checks
- **Expected Result:** frontend job fails on `tsc`; check is red
- **Automation note:** one-time verification at rollout

### TC-9 — secretless CI (covers AC-7)
- **Type:** manual (CI verification)
- **Setup:** repo with no Actions secrets configured
- **Steps:** inspect a green CI run's logs
- **Expected Result:** no step references or requires `GROQ_API_KEY`/`FEC_API_KEY`/`NEWSAPI_KEY`; suite passed without them
- **Automation note:** holds structurally as long as tests keep all upstreams mocked
