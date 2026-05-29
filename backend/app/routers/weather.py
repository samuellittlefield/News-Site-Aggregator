from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClimateEvent, RegionalWeather
from app.routers.climate import CATEGORY_ICONS, CATEGORY_LABELS

router = APIRouter(prefix="/api/weather", tags=["weather"])


# ── Extreme events clustered by type ──────────────────────────────────────────

class ExtremeCluster(BaseModel):
    category: str
    label: str
    icon: str
    count: int
    worst_title: str
    worst_location: Optional[str]
    worst_date: Optional[datetime]
    worst_magnitude: Optional[float]
    worst_magnitude_unit: Optional[str]
    worst_summary: Optional[str]
    worst_source_url: Optional[str]


@router.get("/extreme", response_model=List[ExtremeCluster])
def extreme_clusters(db: Session = Depends(get_db)):
    """EONET events grouped by type — one card per category."""
    events = (
        db.query(ClimateEvent)
        .filter(ClimateEvent.status == "open")
        .order_by(ClimateEvent.start_date.desc().nullslast())
        .all()
    )

    # Group by category
    by_cat: dict[str, list] = {}
    for e in events:
        by_cat.setdefault(e.category, []).append(e)

    clusters = []
    for cat, cat_events in by_cat.items():
        # Pick worst = highest magnitude or most recent
        worst = max(cat_events, key=lambda e: (e.magnitude or 0, e.start_date or datetime.min))
        clusters.append(ExtremeCluster(
            category=cat,
            label=CATEGORY_LABELS.get(cat, cat),
            icon=CATEGORY_ICONS.get(cat, "🌍"),
            count=len(cat_events),
            worst_title=worst.title,
            worst_location=worst.location,
            worst_date=worst.start_date,
            worst_magnitude=worst.magnitude,
            worst_magnitude_unit=worst.magnitude_unit,
            worst_summary=worst.ai_summary,
            worst_source_url=worst.source_url,
        ))

    # Sort by count desc
    clusters.sort(key=lambda c: c.count, reverse=True)
    return clusters


# ── Regional daily weather ─────────────────────────────────────────────────────

class RegionalWeatherOut(BaseModel):
    region: str
    city: str
    temp_max_f: Optional[float]
    temp_min_f: Optional[float]
    precipitation_mm: Optional[float]
    condition: Optional[str]
    fetched_at: datetime

    model_config = {"from_attributes": True}


@router.get("/regional", response_model=List[RegionalWeatherOut])
def regional_weather(db: Session = Depends(get_db)):
    return db.query(RegionalWeather).order_by(RegionalWeather.region).all()
