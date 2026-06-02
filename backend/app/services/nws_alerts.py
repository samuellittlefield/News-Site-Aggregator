import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import NWSAlert

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
NWS_URL = "https://api.weather.gov/alerts/active"


async def fetch_nws_alerts(db: Session) -> "list[NWSAlert]":
    headers = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)", "Accept": "application/geo+json"}
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            resp = await client.get(NWS_URL)
        resp.raise_for_status()
    except httpx.RequestError as e:
        logger.warning("NWS alerts request failed: %s", e)
        return []
    except httpx.HTTPStatusError as e:
        logger.warning("NWS alerts HTTP error %s", e.response.status_code)
        return []

    features = resp.json().get("features", [])
    seen_ids: set[str] = set()
    saved: list[NWSAlert] = []

    for feat in features:
        props = feat.get("properties", {})
        nws_id = props.get("id", "")
        if not nws_id or nws_id in seen_ids:
            continue
        seen_ids.add(nws_id)

        severity = props.get("severity", "Unknown")
        if SEVERITY_RANK.get(severity, 0) < SEVERITY_RANK["Moderate"]:
            continue

        def _parse_dt(val: Optional[str]) -> Optional[datetime]:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                return None

        expires = _parse_dt(props.get("expires"))
        if expires and expires < now:
            continue

        existing = db.query(NWSAlert).filter(NWSAlert.nws_id == nws_id).first()
        if existing:
            existing.severity = severity
            existing.expires = expires
            existing.fetched_at = now
            saved.append(existing)
        else:
            alert = NWSAlert(
                nws_id=nws_id,
                event=props.get("event", "Unknown Event"),
                headline=props.get("headline"),
                severity=severity,
                urgency=props.get("urgency"),
                area_desc=props.get("areaDesc"),
                onset=_parse_dt(props.get("onset")),
                expires=expires,
                fetched_at=now,
            )
            db.add(alert)
            saved.append(alert)

    # Remove expired alerts
    db.query(NWSAlert).filter(
        NWSAlert.expires != None,  # noqa: E711
        NWSAlert.expires < now,
    ).delete(synchronize_session=False)

    db.commit()
    logger.info("NWS alerts: %d active saved", len(saved))
    return saved
