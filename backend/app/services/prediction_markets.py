"""
Prediction markets service (Polymarket Gamma API).

Pulls the top politics markets by 24h volume from the public Gamma API,
upserts them, and appends a price snapshot per run so the frontend can draw
price-history sparklines. The `platform` column leaves room for Kalshi later.

Gamma API quirks: `outcomes` and `outcomePrices` are JSON-encoded *strings*,
not arrays; volume/liquidity come as both strings and numeric (`volumeNum`)
fields — the numeric variants are used here.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import MarketSnapshot, PredictionMarket

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
GAMMA_URL = "https://gamma-api.polymarket.com/markets"
POLITICS_TAG_ID = 2
MIN_VOLUME_24H = 1000.0  # ignore dead markets
MAX_MARKETS = 60
SNAPSHOT_RETENTION_DAYS = 30


def _parse_json_field(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except ValueError:
            return []
    return []


def _parse_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None


async def fetch_polymarket(db: Session) -> int:
    params = {
        "closed": "false",
        "active": "true",
        "limit": MAX_MARKETS,
        "order": "volume24hr",
        "ascending": "false",
        "tag_id": POLITICS_TAG_ID,
        "related_tags": "true",
    }
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
            resp = await client.get(GAMMA_URL, params=params)
        resp.raise_for_status()
        markets = resp.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
        logger.warning("Polymarket fetch failed: %s", e)
        return 0

    if not isinstance(markets, list):
        logger.warning("Polymarket unexpected payload shape")
        return 0

    now = datetime.now(timezone.utc)
    seen_ids: set[str] = set()
    saved = 0

    for m in markets:
        market_id = m.get("id")
        question = (m.get("question") or "").strip()
        if not market_id or not question:
            continue
        volume_24h = m.get("volume24hr") or 0.0
        if volume_24h < MIN_VOLUME_24H:
            continue

        outcome_names = _parse_json_field(m.get("outcomes"))
        outcome_prices = _parse_json_field(m.get("outcomePrices"))
        outcomes = []
        yes_price = None
        for name, price in zip(outcome_names, outcome_prices):
            try:
                price_f = float(price)
            except (TypeError, ValueError):
                continue
            outcomes.append({"name": name, "price": price_f})
            if str(name).lower() == "yes":
                yes_price = price_f

        events = m.get("events") or []
        event_title = (events[0].get("title") or "").strip() if events else None
        slug = m.get("slug")
        # Within a multi-outcome event, groupItemTitle is the outcome label
        # (e.g. "Egypt" in "World Cup Winner") — prefer it for display
        group_title = (m.get("groupItemTitle") or "").strip()
        display_question = f"{event_title}: {group_title}" if event_title and group_title else question

        fields = dict(
            question=display_question,
            slug=slug,
            url=f"https://polymarket.com/event/{events[0]['slug']}" if events and events[0].get("slug") else None,
            event_title=event_title,
            outcomes=outcomes,
            yes_price=yes_price,
            volume_24h=volume_24h,
            liquidity=m.get("liquidityNum"),
            end_date=_parse_date(m.get("endDate")),
            active=True,
            fetched_at=now,
        )

        seen_ids.add(str(market_id))
        existing = db.query(PredictionMarket).filter(
            PredictionMarket.platform == "polymarket",
            PredictionMarket.market_id == str(market_id),
        ).first()
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            market_row = existing
        else:
            market_row = PredictionMarket(platform="polymarket", market_id=str(market_id), **fields)
            db.add(market_row)
            db.flush()  # assign id for the snapshot FK

        db.add(MarketSnapshot(market_id=market_row.id, yes_price=yes_price, captured_at=now))
        saved += 1

    # Markets that dropped out of the top list are no longer shown
    db.query(PredictionMarket).filter(
        PredictionMarket.platform == "polymarket",
        PredictionMarket.market_id.notin_(seen_ids),
        PredictionMarket.active == True,  # noqa: E712
    ).update({"active": False}, synchronize_session=False)

    db.query(MarketSnapshot).filter(
        MarketSnapshot.captured_at < now - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    ).delete(synchronize_session=False)

    db.commit()
    logger.info("Polymarket: %d markets upserted", saved)
    return saved
