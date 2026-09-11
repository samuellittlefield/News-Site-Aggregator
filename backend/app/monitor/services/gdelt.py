"""
GDELT DOC 2.0 API client (https://api.gdeltproject.org/api/v2/doc/doc).

Free, no auth, indexes global news every 15 minutes with a 3-month rolling
window — used as the primary realtime article source (NewsAPI's free tier
delays articles 24h, so it is fallback only).

Quirks handled here:
  - GDELT returns HTTP 200 with a plain-text error body when throttled or
    when a query is malformed, so .json() is guarded.
  - Informal rate limit of ~1 request / 5s, enforced via a module-level lock.
  - `seendate` is "YYYYMMDDTHHMMSSZ", not ISO-8601.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MIN_REQUEST_SPACING = 5.0  # seconds
RATE_LIMIT_COOLDOWN = 120.0  # seconds to back off after a 429

_throttle_lock = asyncio.Lock()
_last_request_at = 0.0
_cooldown_until = 0.0


def _parse_seendate(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def query_gdelt(query: str, timespan: str = "24h", maxrecords: int = 30) -> list[dict]:
    """Run a GDELT ArtList query, returning normalized article dicts."""
    global _last_request_at, _cooldown_until

    if time.monotonic() < _cooldown_until:
        return []

    async with _throttle_lock:
        wait = MIN_REQUEST_SPACING - (time.monotonic() - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_at = time.monotonic()

    params = {
        "query": f"{query} sourcelang:english sourcecountry:US",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": maxrecords,
        "timespan": timespan,
        "sort": "hybridrel",
    }
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
            resp = await client.get(GDELT_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            _cooldown_until = time.monotonic() + RATE_LIMIT_COOLDOWN
            logger.warning("GDELT rate-limited; backing off %.0fs", RATE_LIMIT_COOLDOWN)
        else:
            logger.warning("GDELT HTTP error for %r: %s", query, e)
        return []
    except httpx.RequestError as e:
        logger.warning("GDELT request failed for %r: %s", query, e)
        return []
    except ValueError:
        # 200 with a plain-text error body (throttled or bad query)
        logger.warning("GDELT non-JSON response for %r: %s", query, resp.text[:120])
        return []

    articles = []
    seen_urls: set[str] = set()
    for item in data.get("articles", []):
        url = item.get("url")
        title = (item.get("title") or "").strip()
        if not url or not title or url in seen_urls:
            continue
        seen_urls.add(url)
        articles.append({
            "title": title,
            "url": url,
            "domain": item.get("domain") or "",
            "published_at": _parse_seendate(item.get("seendate")),
        })
    return articles
