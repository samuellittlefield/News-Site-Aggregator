"""Kalshi ingestion upsert idempotency + deactivation (AC-4 / TC-5).

`fetch_kalshi` makes one request per series (CONTROLH, CONTROLS). We mock the
markets endpoint with a side-effect that returns the right series' payload from a
mutable holder, so the same test can replay changed-price and removed-market
variants. Assertions follow TC-5:
  - identical replay → no duplicate PredictionMarket rows
  - changed-price replay → same rows, prices overwritten
  - removed-market replay → the absent market flips active=False
`MarketSnapshot` grows one row per market per run by design (not an idempotency
violation) — asserted explicitly rather than treated as drift.
"""
import copy
import json
import pathlib

import httpx
import pytest

from app.services import kalshi
from app.models import MarketSnapshot, PredictionMarket

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "kalshi_markets.json").read_text()
)


def _kalshi_markets(db):
    return db.query(PredictionMarket).filter(PredictionMarket.platform == "kalshi")


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
