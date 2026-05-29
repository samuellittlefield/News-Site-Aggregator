from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClimateEvent

router = APIRouter(prefix="/api/climate", tags=["climate"])

CATEGORY_LABELS = {
    "wildfires": "Wildfires",
    "severeStorms": "Hurricanes & Storms",
    "floods": "Floods & Heavy Rain",
    "tempExtremes": "Extreme Heat",
    "drought": "Drought",
    "landslides": "Landslides & Mudslides",
}

CATEGORY_ICONS = {
    "wildfires": "🔥",
    "severeStorms": "🌀",
    "floods": "🌊",
    "tempExtremes": "🌡",
    "drought": "☀️",
    "landslides": "⛰️",
}


class ClimateEventOut(BaseModel):
    id: int
    eonet_id: str
    title: str
    category: str
    category_label: str
    category_icon: str
    status: str
    coordinates: Optional[dict]
    start_date: Optional[datetime]
    magnitude: Optional[float]
    magnitude_unit: Optional[str]
    source_url: Optional[str]
    ai_summary: Optional[str]
    location: Optional[str]
    fetched_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=List[ClimateEventOut])
def list_climate_events(db: Session = Depends(get_db)):
    events = (
        db.query(ClimateEvent)
        .filter(ClimateEvent.status == "open")
        .order_by(ClimateEvent.start_date.desc().nullslast(), ClimateEvent.fetched_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for e in events:
        out = ClimateEventOut(
            id=e.id,
            eonet_id=e.eonet_id,
            title=e.title,
            category=e.category,
            category_label=CATEGORY_LABELS.get(e.category, e.category),
            category_icon=CATEGORY_ICONS.get(e.category, "🌍"),
            status=e.status,
            coordinates=e.coordinates,
            start_date=e.start_date,
            magnitude=e.magnitude,
            magnitude_unit=e.magnitude_unit,
            source_url=e.source_url,
            ai_summary=e.ai_summary,
            location=e.location,
            fetched_at=e.fetched_at,
        )
        result.append(out)
    return result
