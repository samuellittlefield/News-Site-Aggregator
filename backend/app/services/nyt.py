"""
New York Times RSS enrichment service.

Fetches NYT feeds and BOOSTS existing Google Trends entries when there is
editorial coverage of the same topic. Never creates standalone Trend entries —
Google Trends is the only source of truth for what's trending.

Returns the number of existing trends that were boosted.
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend

logger = logging.getLogger(__name__)

NYT_FEEDS = [
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MostShared.xml",   "weight": 200, "tag": "nyt_shared"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MostEmailed.xml",  "weight": 180, "tag": "nyt_emailed"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",     "weight": 150, "tag": "nyt_home"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",           "weight": 130, "tag": "nyt_us"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",        "weight": 120, "tag": "nyt_world"},
]

HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _title_overlap(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


async def fetch_nyt_trending(db: Session) -> int:
    """
    Fetches NYT RSS feeds and boosts signal scores of matching active trends.
    Returns the count of trends boosted.
    """
    # Get active Google Trends entries (only source="rss")
    active_trends = (
        db.query(Trend)
        .filter(Trend.is_active == True, Trend.source == "rss")  # noqa
        .all()
    )
    if not active_trends:
        return 0

    active_map = {t.title.lower(): t for t in active_trends}
    boosted_ids: set = set()
    seen_urls: set = set()

    for feed_info in NYT_FEEDS:
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
                resp = await client.get(feed_info["url"])
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            items = channel.findall("item") if channel else []
        except Exception as e:
            logger.warning("NYT feed %s failed: %s", feed_info["tag"], e)
            continue

        for item in items[:20]:
            title = (item.findtext("title") or "").strip()
            url   = (item.findtext("link")  or "").strip()

            if not title or url in seen_urls:
                continue
            seen_urls.add(url)

            # Find best matching active trend
            best_match: Optional[Trend] = None
            best_score = 0.0

            for active_title, trend in active_map.items():
                overlap = _title_overlap(title, active_title)
                if overlap > best_score and overlap >= 0.40:
                    best_score = overlap
                    best_match = trend

            if best_match:
                boost = feed_info["weight"] * 0.6
                best_match.signal_score = best_match.signal_score + boost
                src_list = list(set((best_match.sources_list or []) + [feed_info["tag"]]))
                best_match.sources_list = src_list
                boosted_ids.add(best_match.id)
                logger.debug(
                    "NYT %s boost: '%s' → '%s' +%.0f",
                    feed_info["tag"], title[:40], best_match.title[:40], boost,
                )

    db.commit()
    logger.info("NYT enrichment: boosted %d existing trends", len(boosted_ids))
    return len(boosted_ids)
