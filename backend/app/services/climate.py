import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import ClimateEvent

logger = logging.getLogger(__name__)

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0"}

CATEGORIES = {
    "wildfires": "Wildfires",
    "severeStorms": "Severe Storms",
    "floods": "Floods",
    "tempExtremes": "Extreme Heat",
    "drought": "Drought",
}

CATEGORY_ICONS = {
    "wildfires": "🔥",
    "severeStorms": "⛈",
    "floods": "🌊",
    "tempExtremes": "🌡",
    "drought": "☀️",
}


async def _generate_summary(title: str, category: str, magnitude: Optional[float],
                             unit: Optional[str], api_key: str) -> Optional[str]:
    mag_str = f" Magnitude: {magnitude} {unit}." if magnitude else ""
    prompt = (
        f'Describe this climate event in 1-2 sentences: "{title}". '
        f"Category: {CATEGORIES.get(category, category)}.{mag_str} "
        f"Be factual and concise. Focus on location and impact."
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
            )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


async def fetch_climate_events(db: Session) -> list:
    """Fetch open natural events from NASA EONET, upsert into DB, generate AI summaries."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
            resp = await client.get(
                EONET_URL,
                params={
                    "status": "open",
                    "limit": 50,
                    "days": 30,
                    "category": ",".join(CATEGORIES.keys()),
                },
            )
        resp.raise_for_status()
    except httpx.RequestError as e:
        logger.error("EONET fetch failed: %s", e)
        return []

    events_data = resp.json().get("events", [])
    api_key = os.getenv("GROQ_API_KEY")
    now = datetime.now(timezone.utc)
    saved = []

    for event in events_data:
        eonet_id = event.get("id")
        title = event.get("title", "")
        if not eonet_id or not title:
            continue

        # Get category
        cats = event.get("categories", [])
        category = cats[0]["id"] if cats else "unknown"
        if category not in CATEGORIES:
            continue

        # Get most recent geometry
        geometries = event.get("geometry", [])
        coords = None
        start_date = None
        magnitude = None
        magnitude_unit = None
        if geometries:
            geo = geometries[-1]
            if geo.get("type") == "Point":
                coords = {"lon": geo["coordinates"][0], "lat": geo["coordinates"][1]}
            if geo.get("date"):
                try:
                    start_date = datetime.fromisoformat(geo["date"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            magnitude = geo.get("magnitudeValue")
            magnitude_unit = geo.get("magnitudeUnit")

        # Get source URL
        sources = event.get("sources", [])
        source_url = sources[0]["url"] if sources else None

        # Upsert
        existing = db.query(ClimateEvent).filter(ClimateEvent.eonet_id == eonet_id).first()
        if existing:
            existing.title = title
            existing.status = event.get("closed") and "closed" or "open"
            existing.coordinates = coords
            existing.start_date = start_date
            existing.magnitude = magnitude
            existing.magnitude_unit = magnitude_unit
            existing.source_url = source_url
            existing.fetched_at = now
            climate_event = existing
        else:
            climate_event = ClimateEvent(
                eonet_id=eonet_id,
                title=title,
                category=category,
                status="open",
                coordinates=coords,
                start_date=start_date,
                magnitude=magnitude,
                magnitude_unit=magnitude_unit,
                source_url=source_url,
                fetched_at=now,
            )
            db.add(climate_event)
            db.flush()

        # Generate AI summary only if missing
        if not climate_event.ai_summary and api_key:
            summary = await _generate_summary(title, category, magnitude, magnitude_unit, api_key)
            if summary:
                climate_event.ai_summary = summary

        saved.append(climate_event)

    db.commit()
    logger.info("Climate: saved %d events from EONET", len(saved))
    return saved
