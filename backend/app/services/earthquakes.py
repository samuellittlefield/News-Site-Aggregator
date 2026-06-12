"""
USGS earthquake feed service.

Pulls the rolling GeoJSON summary feeds (updated every minute by USGS):
  - all M2.5+ in the last day (primary signal)
  - all M4.5+ in the last week (context for the hazards drill-in page)

Upserts by USGS event id — USGS revises magnitudes after initial publication,
so existing rows are updated in place. Rows older than 7 days are pruned.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Earthquake

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
FEED_URLS = [
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
]


async def fetch_earthquakes(db: Session) -> int:
    now = datetime.now(timezone.utc)
    features: dict[str, dict] = {}

    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
        for url in FEED_URLS:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                for feat in resp.json().get("features", []):
                    fid = feat.get("id")
                    if fid:
                        features[fid] = feat
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
                logger.warning("USGS feed failed (%s): %s", url, e)

    if not features:
        return 0

    existing = {
        q.usgs_id: q for q in
        db.query(Earthquake).filter(Earthquake.usgs_id.in_(features.keys())).all()
    }

    saved = 0
    for fid, feat in features.items():
        props = feat.get("properties", {})
        coords = (feat.get("geometry") or {}).get("coordinates") or [None, None, None]
        time_ms = props.get("time")
        fields = dict(
            magnitude=props.get("mag"),
            place=props.get("place"),
            time=datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc) if time_ms else None,
            lng=coords[0],
            lat=coords[1],
            depth_km=coords[2],
            alert_level=props.get("alert"),
            tsunami=bool(props.get("tsunami")),
            felt=props.get("felt"),
            url=props.get("url"),
            fetched_at=now,
        )
        quake = existing.get(fid)
        if quake:
            for k, v in fields.items():
                setattr(quake, k, v)
        else:
            db.add(Earthquake(usgs_id=fid, **fields))
        saved += 1

    db.query(Earthquake).filter(
        Earthquake.time < now - timedelta(days=7)
    ).delete(synchronize_session=False)

    db.commit()
    logger.info("Earthquakes: %d upserted", saved)
    return saved
