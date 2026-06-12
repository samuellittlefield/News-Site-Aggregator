"""
FAA national airspace status service.

Fetches https://nasstatus.faa.gov/api/airport-status-information — which returns
XML despite the /api/ path — and normalizes ground stops, ground delays,
arrival/departure delays, and airport closures into flat event dicts.

Pure current-state data with no history value, so it lives in a module-level
in-memory cache rather than the DB. This is safe because the scheduler runs in
the same single uvicorn process as the API; promote to a DB table (modeled on
ServiceStatus) if the deployment ever moves to multiple workers.
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
FAA_URL = "https://nasstatus.faa.gov/api/airport-status-information"

_CACHE: dict = {"events": [], "fetched_at": None}


def _text(node: Optional[ET.Element], tag: str) -> Optional[str]:
    if node is None:
        return None
    child = node.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _parse_events(root: ET.Element) -> list[dict]:
    events: list[dict] = []

    for program in root.iter("Program"):  # ground stops
        events.append({
            "airport": _text(program, "ARPT"),
            "type": "ground_stop",
            "reason": _text(program, "Reason"),
            "avg_delay": None,
            "end_time": _text(program, "End_Time"),
        })

    for gd in root.iter("Ground_Delay"):
        events.append({
            "airport": _text(gd, "ARPT"),
            "type": "ground_delay",
            "reason": _text(gd, "Reason"),
            "avg_delay": _text(gd, "Avg"),
            "end_time": None,
        })

    for delay in root.iter("Delay"):  # general arrival/departure delays
        ad = delay.find("Arrival_Departure")
        kind = ad.get("Type", "").lower() if ad is not None else ""
        events.append({
            "airport": _text(delay, "ARPT"),
            "type": f"{kind}_delay" if kind else "delay",
            "reason": _text(delay, "Reason"),
            "avg_delay": _text(ad, "Max") if ad is not None else None,
            "end_time": None,
        })

    for airport in root.iter("Airport"):  # closures (includes long-lived GA NOTAMs)
        events.append({
            "airport": _text(airport, "ARPT"),
            "type": "closure",
            "reason": _text(airport, "Reason"),
            "avg_delay": None,
            "end_time": _text(airport, "Reopen"),
        })

    return [e for e in events if e["airport"]]


async def fetch_faa_status() -> list[dict]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
            resp = await client.get(FAA_URL)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except (httpx.RequestError, httpx.HTTPStatusError, ET.ParseError) as e:
        logger.warning("FAA status fetch failed: %s", e)
        return _CACHE["events"]

    events = _parse_events(root)
    _CACHE["events"] = events
    _CACHE["fetched_at"] = datetime.now(timezone.utc)
    logger.info("FAA status: %d events", len(events))
    return events


def get_cached_status() -> dict:
    return {"events": _CACHE["events"], "fetched_at": _CACHE["fetched_at"]}
