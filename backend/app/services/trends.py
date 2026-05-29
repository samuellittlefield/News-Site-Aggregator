import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Trend, TrendSnapshot

logger = logging.getLogger(__name__)

TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=US"
HT_NS = "https://trends.google.com/trending/rss"

# Traffic string → signal score.
# RSS entries represent *confirmed* high-volume searches so they score
# competitively alongside Wikipedia/Reddit spike signals.
TRAFFIC_SIGNAL: dict = {
    "200": 60, "500": 100, "1000": 160, "2000": 230, "5000": 320,
    "10K": 450, "50K": 700, "100K": 950, "500K": 1500, "1M": 2000,
}

def _traffic_to_signal(traffic: str) -> float:
    """Convert a traffic string like '2000+' or '10K+' to a signal score."""
    if not traffic:
        return 50.0
    key = traffic.strip().rstrip("+").upper()
    return float(TRAFFIC_SIGNAL.get(key, 50))


def _ht(tag: str) -> str:
    return f"{{{HT_NS}}}{tag}"


async def fetch_trends(db: Session) -> list:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(TRENDS_RSS_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    channel = root.find("channel")
    if channel is None:
        logger.warning("No <channel> in Google Trends RSS")
        return []

    # Deactivate all current active trends before re-activating matched ones
    db.query(Trend).filter(Trend.is_active == True).update({"is_active": False})  # noqa: E712

    trends = []
    for rank, item in enumerate(channel.findall("item"), start=1):
        title = (item.findtext("title") or "").strip()
        traffic = (item.findtext(_ht("approx_traffic")) or "").strip()

        if not title:
            continue

        existing = db.query(Trend).filter(Trend.title == title).first()
        now = datetime.now(timezone.utc)
        signal = _traffic_to_signal(traffic)

        if existing:
            existing.is_active = True
            existing.fetched_at = now
            existing.traffic_volume = traffic
            existing.signal_score = signal
            existing.appearance_count = (existing.appearance_count or 0) + 1
            trend = existing
        else:
            trend = Trend(
                title=title,
                traffic_volume=traffic,
                geo="US",
                is_active=True,
                first_seen_at=now,
                appearance_count=1,
                signal_score=signal,
            )
            db.add(trend)
            db.flush()

        db.add(TrendSnapshot(trend_id=trend.id, traffic_volume=traffic, rank=rank, captured_at=now))

        # Parse articles embedded in the RSS item — no external API needed
        db.query(Article).filter(Article.trend_id == trend.id).delete()
        for news_item in item.findall(_ht("news_item")):
            headline = (news_item.findtext(_ht("news_item_title")) or "").strip()
            url = (news_item.findtext(_ht("news_item_url")) or "").strip()
            source = (news_item.findtext(_ht("news_item_source")) or "").strip()
            snippet = (news_item.findtext(_ht("news_item_snippet")) or "").strip()
            if headline and url:
                db.add(Article(
                    trend_id=trend.id,
                    headline=headline[:500],
                    url=url,
                    source=source,
                    description=snippet or None,
                ))

        trends.append(trend)

    db.commit()
    logger.info("Fetched %d trends from Google Trends RSS", len(trends))
    return trends
