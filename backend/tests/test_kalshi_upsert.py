"""Kalshi ingestion upsert idempotency + deactivation (AC-4 / TC-5), plus
fetch-failure handling (kalshi-fetch-failure).

`fetch_kalshi` makes one request per series (CONTROLH, CONTROLS). We mock the
markets endpoint with a side-effect that returns the right series' payload from a
mutable holder, so the same test can replay changed-price and removed-market
variants. Assertions follow TC-5:
  - identical replay → no duplicate PredictionMarket rows
  - changed-price replay → same rows, prices overwritten
  - removed-market replay → the absent market flips active=False
`MarketSnapshot` grows one row per market per run by design (not an idempotency
violation) — asserted explicitly rather than treated as drift.

2026-09-12 incident (kalshi-fetch-failure): both series started raising
HTTPStatusError, `fetch_kalshi` swallowed it and returned 0, and
`notin_(seen_ids)` against an empty set flipped every stored market inactive
— one upstream blip retired the whole platform and the scheduler recorded a
clean `success`/`item_count: 0`, indistinguishable from a quiet day. Upstream
recovered on its own within the hour (confirmed live: item_count back to 4,
House market back near 85% D), so this covers the two defects with a mocked
403 rather than chasing the live connectivity issue — TC-1 through TC-4.
"""
import copy
import json
import pathlib

import httpx
import pytest

from app import scheduler
from app.elections.services import kalshi
from app.models import MarketSnapshot, PredictionMarket, SourceRun

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "kalshi_markets.json").read_text()
)


def _kalshi_markets(db):
    return db.query(PredictionMarket).filter(PredictionMarket.platform == "kalshi")


def _seed_active_markets(db, tickers):
    for ticker in tickers:
        db.add(PredictionMarket(
            platform="kalshi", market_id=ticker, question=ticker,
            outcomes=[], yes_price=0.5, active=True,
        ))
    db.commit()


@pytest.fixture
def mock_kalshi(respx_router):
    """Mock the markets endpoint; `holder['data']` is swapped between runs to
    simulate updated upstream responses."""
    holder = {"data": copy.deepcopy(FIXTURE)}

    def _responder(request: httpx.Request) -> httpx.Response:
        series = request.url.params.get("series_ticker")
        return httpx.Response(200, json=holder["data"].get(series, {"markets": []}))

    respx_router.get(kalshi.MARKETS_URL).mock(side_effect=_responder)
    return holder


async def test_kalshi_upsert_is_idempotent_and_deactivates(db, mock_kalshi):
    # ── Run 1: base fixture ─────────────────────────────────────────────────
    saved = await kalshi.fetch_kalshi(db)
    assert saved == 4  # 2 House + 2 Senate; the low-volume 2028 market is filtered
    assert _kalshi_markets(db).count() == 4
    # MIN_VOLUME_24H filter dropped the dormant out-year market.
    assert _kalshi_markets(db).filter(PredictionMarket.market_id == "CONTROLH-2028-D").count() == 0
    house_d = _kalshi_markets(db).filter(PredictionMarket.market_id == "CONTROLH-2026-D").one()
    assert house_d.yes_price == 0.55
    assert house_d.active is True

    # ── Run 2: identical fixture → no new rows (idempotent upsert) ───────────
    await kalshi.fetch_kalshi(db)
    assert _kalshi_markets(db).count() == 4
    # Snapshots grow one-per-market-per-run by design: 4 + 4 after two runs.
    assert db.query(MarketSnapshot).count() == 8

    # ── Run 3: changed price → same rows, price overwritten ─────────────────
    changed = copy.deepcopy(FIXTURE)
    changed["CONTROLH"]["markets"][0]["last_price_dollars"] = "0.62"
    mock_kalshi["data"] = changed
    await kalshi.fetch_kalshi(db)
    assert _kalshi_markets(db).count() == 4
    db.expire_all()
    assert _kalshi_markets(db).filter(
        PredictionMarket.market_id == "CONTROLH-2026-D"
    ).one().yes_price == 0.62

    # ── Run 4: market removed → row flips active=False (retirement sweep) ────
    removed = copy.deepcopy(FIXTURE)
    removed["CONTROLH"]["markets"] = [
        m for m in removed["CONTROLH"]["markets"] if m["ticker"] != "CONTROLH-2026-R"
    ]
    mock_kalshi["data"] = removed
    await kalshi.fetch_kalshi(db)
    assert _kalshi_markets(db).count() == 4  # deactivated, not deleted
    db.expire_all()
    assert _kalshi_markets(db).filter(
        PredictionMarket.market_id == "CONTROLH-2026-R"
    ).one().active is False
    # A still-present market stays active.
    assert _kalshi_markets(db).filter(
        PredictionMarket.market_id == "CONTROLS-2026-D"
    ).one().active is True


# ── TC-1: both series failing raises, doesn't return a hollow 0 (AC-1) ──────

async def test_all_series_failing_raises(db, respx_router):
    respx_router.get(kalshi.MARKETS_URL).mock(return_value=httpx.Response(403))

    with pytest.raises(Exception) as exc_info:
        await kalshi.fetch_kalshi(db)

    assert "CONTROLH" in str(exc_info.value)
    assert "CONTROLS" in str(exc_info.value)


async def test_all_series_failing_records_sourcerun_failure_not_success(db, monkeypatch):
    """End-to-end through the scheduler wrapper — the actual bug: a swallowed
    total failure recorded status: success, item_count: 0 for a full day
    before anyone noticed."""
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    async def _boom(_db):
        raise RuntimeError("Kalshi fetch failed for all series: CONTROLH: 403; CONTROLS: 403")

    monkeypatch.setattr(scheduler.kalshi_service, "fetch_kalshi", _boom)

    await scheduler.refresh_kalshi()

    row = db.query(SourceRun).filter(SourceRun.source_id == "kalshi_job").one()
    assert row.status == "failure"
    assert row.item_count is None
    assert "403" in (row.error_message or "")


# ── TC-2: one series up, one down — still records what it got (AC-2) ───────

async def test_partial_failure_saves_the_healthy_series(db, respx_router, caplog):
    import logging

    def _responder(request: httpx.Request) -> httpx.Response:
        series = request.url.params.get("series_ticker")
        if series == "CONTROLH":
            return httpx.Response(200, json=FIXTURE["CONTROLH"])
        return httpx.Response(503)

    respx_router.get(kalshi.MARKETS_URL).mock(side_effect=_responder)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.kalshi"):
        saved = await kalshi.fetch_kalshi(db)

    assert saved == 2  # CONTROLH's 2 qualifying markets; the 2028 one is filtered
    assert _kalshi_markets(db).count() == 2
    assert any("CONTROLS" in r.getMessage() for r in caplog.records)


# ── TC-3: a failed fetch never retires existing markets (AC-3) ─────────────

async def test_failed_fetch_does_not_retire_existing_markets(db, respx_router):
    _seed_active_markets(db, ["CONTROLH-2026-D", "CONTROLH-2026-R", "CONTROLS-2026-D", "CONTROLS-2026-R"])
    respx_router.get(kalshi.MARKETS_URL).mock(return_value=httpx.Response(403))

    with pytest.raises(Exception):
        await kalshi.fetch_kalshi(db)

    db.expire_all()
    assert _kalshi_markets(db).filter(PredictionMarket.active == True).count() == 4  # noqa: E712


async def test_partial_failure_does_not_retire_the_down_series_markets(db, respx_router):
    """The narrower AC-3 case: CONTROLH fetches fine (its markets stay seen),
    CONTROLS 503s. seen_ids never gains a CONTROLS ticker on this run, so a
    naive notin_(seen_ids) would retire CONTROLS-2026-D/R even though nothing
    said they disappeared — they just couldn't be asked about."""
    _seed_active_markets(db, ["CONTROLS-2026-D", "CONTROLS-2026-R"])

    def _responder(request: httpx.Request) -> httpx.Response:
        series = request.url.params.get("series_ticker")
        if series == "CONTROLH":
            return httpx.Response(200, json=FIXTURE["CONTROLH"])
        return httpx.Response(503)

    respx_router.get(kalshi.MARKETS_URL).mock(side_effect=_responder)
    await kalshi.fetch_kalshi(db)

    db.expire_all()
    assert _kalshi_markets(db).filter(
        PredictionMarket.market_id.in_(["CONTROLS-2026-D", "CONTROLS-2026-R"])
    ).filter(PredictionMarket.active == True).count() == 2  # noqa: E712


# ── AC-8: volume filter and series are unchanged ────────────────────────────

def test_min_volume_and_series_unchanged():
    assert kalshi.MIN_VOLUME_24H == 1000.0
    assert set(kalshi.SERIES.keys()) == {"CONTROLH", "CONTROLS"}


# ── TC-13: a Kalshi failure doesn't starve Polymarket's run ─────────────────

async def test_kalshi_failure_does_not_affect_markets_job(db, monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    async def _boom(_db):
        raise RuntimeError("Kalshi fetch failed for all series: CONTROLH: 403; CONTROLS: 403")

    async def _ok_polymarket(_db):
        return 60

    monkeypatch.setattr(scheduler.kalshi_service, "fetch_kalshi", _boom)
    monkeypatch.setattr(scheduler.prediction_markets_service, "fetch_polymarket", _ok_polymarket)

    await scheduler.refresh_kalshi()
    await scheduler.refresh_markets()

    kalshi_run = db.query(SourceRun).filter(SourceRun.source_id == "kalshi_job").one()
    assert kalshi_run.status == "failure"

    markets_run = db.query(SourceRun).filter(SourceRun.source_id == "markets_job").one()
    assert markets_run.status == "success"
    assert markets_run.item_count == 60
