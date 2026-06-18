"""
Kalshi prediction-markets service (control-of-Congress).

Pulls the "control of the House" (CONTROLH) and "control of the Senate"
(CONTROLS) market series from Kalshi's public trade API and upserts them into
the same `PredictionMarket` table Polymarket uses (platform="kalshi"), with a
price snapshot per run for sparklines. No auth is needed for market data; the
public read endpoints allow ~30 req/s.

Kalshi quirks handled here: prices arrive as decimal *dollar* strings 0–1
(`last_price_dollars`, `yes_bid_dollars`, `yes_ask_dollars`), not cents;
`volume_24h_fp`/`liquidity_dollars` also come as strings. Each chamber/year is
its own event (e.g. CONTROLH-2026) with one market per party
(CONTROLH-2026-D / CONTROLH-2026-R), and `yes_sub_title` names the party.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import MarketSnapshot, PredictionMarket

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"
# Control-of-Congress series → display title used to group with Polymarket.
SERIES = {
    "CONTROLH": "Control of the House",
    "CONTROLS": "Control of the Senate",
}
MIN_VOLUME_24H = 1000.0  # drops the dormant out-year (e.g. 2028) markets
SNAPSHOT_RETENTION_DAYS = 30


def _to_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None


def _yes_price(m: dict) -> Optional[float]:
    """Consensus probability: last trade, else midpoint of the yes bid/ask."""
    last = _to_float(m.get("last_price_dollars"))
    if last and last > 0:
        return round(last, 4)
    bid = _to_float(m.get("yes_bid_dollars"))
    ask = _to_float(m.get("yes_ask_dollars"))
    if bid is not None and ask is not None and (bid or ask):
        return round((bid + ask) / 2, 4)
    return None


async def fetch_kalshi(db: Session) -> int:
    now = datetime.now(timezone.utc)
    seen_ids: set[str] = set()
    saved = 0

    for series_ticker, event_title in SERIES.items():
        params = {"series_ticker": series_ticker, "status": "open", "limit": 50}
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
                resp = await client.get(MARKETS_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            logger.warning("Kalshi fetch failed (%s): %s", series_ticker, e)
            continue

        markets = payload.get("markets") if isinstance(payload, dict) else None
        if not isinstance(markets, list):
            logger.warning("Kalshi unexpected payload shape for %s", series_ticker)
            continue

        for m in markets:
            ticker = m.get("ticker")
            title = (m.get("title") or "").strip()
            if not ticker or not title:
                continue
            volume_24h = _to_float(m.get("volume_24h_fp")) or 0.0
            if volume_24h < MIN_VOLUME_24H:
                continue

            yes_price = _yes_price(m)
            outcomes = [
                {"name": "Yes", "price": yes_price},
                {"name": "No", "price": round(1 - yes_price, 4) if yes_price is not None else None},
            ]

            fields = dict(
                question=title,
                slug=ticker.lower(),
                url=f"https://kalshi.com/markets/{series_ticker.lower()}",
                event_title=event_title,
                outcomes=outcomes,
                yes_price=yes_price,
                volume_24h=volume_24h,
                liquidity=_to_float(m.get("liquidity_dollars")),
                end_date=_parse_date(m.get("close_time")),
                active=True,
                fetched_at=now,
            )

            seen_ids.add(str(ticker))
            existing = db.query(PredictionMarket).filter(
                PredictionMarket.platform == "kalshi",
                PredictionMarket.market_id == str(ticker),
            ).first()
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                market_row = existing
            else:
                market_row = PredictionMarket(platform="kalshi", market_id=str(ticker), **fields)
                db.add(market_row)
                db.flush()  # assign id for the snapshot FK

            db.add(MarketSnapshot(market_id=market_row.id, yes_price=yes_price, captured_at=now))
            saved += 1

    # Retire any Kalshi market no longer returned (e.g. resolved/closed)
    db.query(PredictionMarket).filter(
        PredictionMarket.platform == "kalshi",
        PredictionMarket.market_id.notin_(seen_ids),
        PredictionMarket.active == True,  # noqa: E712
    ).update({"active": False}, synchronize_session=False)

    db.query(MarketSnapshot).filter(
        MarketSnapshot.captured_at < now - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    ).delete(synchronize_session=False)

    db.commit()
    logger.info("Kalshi: %d markets upserted", saved)
    return saved
