from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MarketSnapshot, PredictionMarket

router = APIRouter(prefix="/api/markets", tags=["markets"])


class MarketOut(BaseModel):
    id: int
    platform: str
    market_id: str
    question: str
    slug: Optional[str]
    url: Optional[str]
    event_title: Optional[str]
    outcomes: list
    yes_price: Optional[float]
    volume_24h: Optional[float]
    liquidity: Optional[float]
    end_date: Optional[datetime]
    fetched_at: datetime

    model_config = {"from_attributes": True}


class SnapshotOut(BaseModel):
    yes_price: Optional[float]
    captured_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=List[MarketOut])
def list_markets(limit: int = Query(30, le=100), db: Session = Depends(get_db)):
    markets = (
        db.query(PredictionMarket)
        .filter(PredictionMarket.active == True)  # noqa: E712
        .order_by(PredictionMarket.volume_24h.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [MarketOut.model_validate(m) for m in markets]


@router.get("/{market_id}/history", response_model=List[SnapshotOut])
def market_history(market_id: int, days: int = Query(14, le=30), db: Session = Depends(get_db)):
    market = db.query(PredictionMarket).filter(PredictionMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    snaps = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.market_id == market_id, MarketSnapshot.captured_at >= cutoff)
        .order_by(MarketSnapshot.captured_at.asc())
        .all()
    )
    return [SnapshotOut.model_validate(s) for s in snaps]
