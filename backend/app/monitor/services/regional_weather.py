import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import RegionalWeather

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Representative cities per US region
REGIONS = [
    {"region": "West Coast",  "city": "San Francisco", "lat": 37.77,  "lon": -122.42},
    {"region": "Southwest",   "city": "Phoenix",        "lat": 33.45,  "lon": -112.07},
    {"region": "Mountain",    "city": "Denver",         "lat": 39.74,  "lon": -104.98},
    {"region": "Midwest",     "city": "Chicago",        "lat": 41.88,  "lon": -87.63},
    {"region": "South",       "city": "Atlanta",        "lat": 33.75,  "lon": -84.39},
    {"region": "Northeast",   "city": "New York",       "lat": 40.71,  "lon": -74.01},
]

WMO_CONDITIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
}


def _c_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


async def fetch_regional_weather(db: Session) -> list:
    now = datetime.now(timezone.utc)
    results = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for region_info in REGIONS:
            try:
                resp = await client.get(
                    OPEN_METEO_URL,
                    params={
                        "latitude": region_info["lat"],
                        "longitude": region_info["lon"],
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
                        "temperature_unit": "celsius",
                        "timezone": "auto",
                        "forecast_days": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                daily = data.get("daily", {})

                temp_max = daily.get("temperature_2m_max", [None])[0]
                temp_min = daily.get("temperature_2m_min", [None])[0]
                precip = daily.get("precipitation_sum", [None])[0]
                wmo = daily.get("weathercode", [None])[0]
                condition = WMO_CONDITIONS.get(wmo, "Unknown") if wmo is not None else None

                existing = db.query(RegionalWeather).filter(
                    RegionalWeather.region == region_info["region"]
                ).first()

                if existing:
                    existing.temp_max_f = _c_to_f(temp_max) if temp_max is not None else None
                    existing.temp_min_f = _c_to_f(temp_min) if temp_min is not None else None
                    existing.precipitation_mm = precip
                    existing.condition = condition
                    existing.fetched_at = now
                    results.append(existing)
                else:
                    rw = RegionalWeather(
                        region=region_info["region"],
                        city=region_info["city"],
                        latitude=region_info["lat"],
                        longitude=region_info["lon"],
                        temp_max_f=_c_to_f(temp_max) if temp_max is not None else None,
                        temp_min_f=_c_to_f(temp_min) if temp_min is not None else None,
                        precipitation_mm=precip,
                        condition=condition,
                        fetched_at=now,
                    )
                    db.add(rw)
                    results.append(rw)

            except Exception as e:
                logger.warning("Regional weather fetch failed for %s: %s", region_info["city"], e)

    db.commit()
    logger.info("Regional weather: updated %d regions", len(results))
    return results
