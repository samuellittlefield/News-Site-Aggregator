from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
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


REGION_ORDER = ["West Coast", "Southwest", "Mountain", "Midwest", "South", "Northeast"]


@router.get("/regional", response_model=List[RegionalWeatherOut])
def regional_weather(db: Session = Depends(get_db)):
    rows = db.query(RegionalWeather).all()
    rows.sort(key=lambda r: REGION_ORDER.index(r.region) if r.region in REGION_ORDER else 99)
    return rows


# ── 3-day forecast (fetched on demand) ────────────────────────────────────────

WMO_CONDITIONS = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Showers", 81: "Showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Severe thunderstorm",
}

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class DayForecast(BaseModel):
    date: str
    day_name: str
    temp_max_f: Optional[float]
    temp_min_f: Optional[float]
    precipitation_mm: Optional[float]
    wind_mph: Optional[float]
    condition: Optional[str]


class RegionalForecastOut(BaseModel):
    region: str
    city: str
    days: List[DayForecast]


def _c_to_f(c: Optional[float]) -> Optional[float]:
    return round(c * 9 / 5 + 32, 1) if c is not None else None


@router.get("/forecast/{region}", response_model=RegionalForecastOut)
async def get_forecast(region: str, db: Session = Depends(get_db)):
    rw = db.query(RegionalWeather).filter(RegionalWeather.region == region).first()
    if not rw:
        raise HTTPException(status_code=404, detail="Region not found")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": rw.latitude,
                    "longitude": rw.longitude,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
                    "temperature_unit": "celsius",
                    "windspeed_unit": "mph",
                    "timezone": "auto",
                    "forecast_days": 3,
                },
            )
        resp.raise_for_status()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=str(e))

    daily = resp.json().get("daily", {})
    dates = daily.get("time", [])
    days = []
    for i, date_str in enumerate(dates[:3]):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        wmo = (daily.get("weathercode") or [])[i] if i < len(daily.get("weathercode") or []) else None
        days.append(DayForecast(
            date=date_str,
            day_name=DAY_NAMES[dt.weekday()],
            temp_max_f=_c_to_f((daily.get("temperature_2m_max") or [])[i] if i < len(daily.get("temperature_2m_max") or []) else None),
            temp_min_f=_c_to_f((daily.get("temperature_2m_min") or [])[i] if i < len(daily.get("temperature_2m_min") or []) else None),
            precipitation_mm=(daily.get("precipitation_sum") or [])[i] if i < len(daily.get("precipitation_sum") or []) else None,
            wind_mph=(daily.get("windspeed_10m_max") or [])[i] if i < len(daily.get("windspeed_10m_max") or []) else None,
            condition=WMO_CONDITIONS.get(wmo) if wmo is not None else None,
        ))

    return RegionalForecastOut(region=rw.region, city=rw.city, days=days)
