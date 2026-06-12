from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Earthquake
from app.services import faa_status as faa_service

router = APIRouter(prefix="/api/hazards", tags=["hazards"])


class EarthquakeOut(BaseModel):
    id: int
    usgs_id: str
    magnitude: Optional[float]
    place: Optional[str]
    time: Optional[datetime]
    lat: Optional[float]
    lng: Optional[float]
    depth_km: Optional[float]
    alert_level: Optional[str]
    tsunami: bool
    felt: Optional[int]
    url: Optional[str]

    model_config = {"from_attributes": True}


class EarthquakesOut(BaseModel):
    summary: dict
    earthquakes: List[EarthquakeOut]


class FaaEventOut(BaseModel):
    airport: str
    type: str
    reason: Optional[str]
    avg_delay: Optional[str]
    end_time: Optional[str]


class FaaStatusOut(BaseModel):
    events: List[FaaEventOut]
    fetched_at: Optional[datetime]


@router.get("/earthquakes", response_model=EarthquakesOut)
def list_earthquakes(
    min_mag: float = Query(2.5),
    hours: int = Query(24, le=24 * 7),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    quakes = (
        db.query(Earthquake)
        .filter(Earthquake.time >= cutoff, Earthquake.magnitude >= min_mag)
        .order_by(Earthquake.time.desc())
        .limit(200)
        .all()
    )
    mags = [q.magnitude for q in quakes if q.magnitude is not None]
    significant = next((q for q in quakes if (q.magnitude or 0) >= 5.0), None)
    summary = {
        "count": len(quakes),
        "max_magnitude": max(mags) if mags else None,
        "significant": EarthquakeOut.model_validate(significant) if significant else None,
    }
    return EarthquakesOut(
        summary=summary,
        earthquakes=[EarthquakeOut.model_validate(q) for q in quakes],
    )


@router.get("/faa", response_model=FaaStatusOut)
async def get_faa_status():
    cached = faa_service.get_cached_status()
    if cached["fetched_at"] is None:
        # Cold start — fetch on demand so the dashboard isn't empty
        await faa_service.fetch_faa_status()
        cached = faa_service.get_cached_status()
    return FaaStatusOut(**cached)
