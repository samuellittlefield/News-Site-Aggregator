"""
New York Times RSS enrichment service.

Two roles:
1. BOOST existing Google Trends entries when NYT is covering the same topic.
2. CREATE standalone Trend entries for MostShared/MostEmailed stories that
   have no Google Trends match — giving them carousel representation even if
   Google hasn't picked them up yet.

Returns the number of existing trends that were boosted.
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend
from app.services.topic_matcher import find_match

logger = logging.getLogger(__name__)

NYT_FEEDS = [
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MostShared.xml",   "weight": 200, "tag": "nyt_shared",   "standalone": True},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MostEmailed.xml",  "weight": 180, "tag": "nyt_emailed",  "standalone": True},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",     "weight": 150, "tag": "nyt_home",     "standalone": False},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",           "weight": 130, "tag": "nyt_us",       "standalone": False},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",        "weight": 120, "tag": "nyt_world",    "standalone": False},
]

HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}
MAX_STANDALONE = 5  # max new NYT-sourced trends per run


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


async def fetch_nyt_trending(db: Session) -> int:
    """
    Fetches NYT RSS feeds, boosts matching active trends, and creates standalone
    entries for high-confidence NYT stories not covered by Google Trends.
    Returns the count of existing trends boosted.
    """
    active_trends = (
        db.query(Trend)
        .filter(Trend.is_active == True)  # noqa
        .all()
    )

    boosted_ids: set = set()
    seen_titles: set = set()
    standalone_created = 0
    now = datetime.now(timezone.utc)

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
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            match = find_match(title, active_trends, threshold=0.40)

            if match:
                # Boost existing trend
                boost = feed_info["weight"] * 0.6
                match.signal_score += boost
                match.sources_list = list(set((match.sources_list or []) + [feed_info["tag"]]))
                boosted_ids.add(match.id)
                logger.debug("NYT %s boost: '%s' → '%s' +%.0f", feed_info["tag"], title[:40], match.title[:40], boost)
            elif feed_info["standalone"] and standalone_created < MAX_STANDALONE:
                # No Google match — create a standalone entry from high-confidence feeds
                base_signal = feed_info["weight"] * 0.6  # MostShared→120, MostEmailed→108
                description = _strip_html(item.findtext("description") or "")
                trend = Trend(
                    title=title,
                    source="nyt",
                    is_active=True,
                    first_seen_at=now,
                    fetched_at=now,
                    appearance_count=1,
                    signal_score=base_signal,
                    sources_list=[feed_info["tag"]],
                    geo="US",
                    traffic_volume=None,
                )
                db.add(trend)
                # Add to active_trends so subsequent feeds can match against it
                active_trends.append(trend)
                standalone_created += 1
                logger.info("NYT standalone: '%s' (%.0f signal)", title[:60], base_signal)

    db.commit()
    logger.info("NYT enrichment: boosted %d existing trends, created %d standalone", len(boosted_ids), standalone_created)
    return len(boosted_ids)
