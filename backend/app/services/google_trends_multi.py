"""
Multi-window Google Trends service.

Fetches both the 4-hour realtime feed and the 24-hour daily feed,
cross-references them, and produces signal-scored Trend records.

4h feed  → "Breaking" (topic just erupted, very high velocity)
24h feed → "Sustained" (still trending across the day)
Both     → highest confidence signal (cross-validated)
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Summary, Trend, TrendSnapshot

logger = logging.getLogger(__name__)

RSS_24H = "https://trends.google.com/trending/rss?geo=US"
RSS_4H  = "https://trends.google.com/trending/rss?geo=US&hours=4"
HT_NS   = "https://trends.google.com/trending/rss"

# Base signal per window — traffic bonus is added on top
SIGNAL_4H_ONLY  = 280   # Hot right now, very fresh
SIGNAL_24H_ONLY = 160   # Trending today
SIGNAL_BOTH     = 380   # Cross-validated across windows

# Traffic bonus lookup (additive on top of base)
_TRAFFIC_BONUS = {
    "200":   40,  "500":   80,  "1000":  130,  "2000":  190,
    "5000":  270, "10K":   380, "50K":   620,  "100K":  860,
    "200K": 1100, "500K": 1450, "1M":   1800,  "2M":   2300,
    "5M":   2900, "10M":  3700,
}


def _ht(tag: str) -> str:
    return f"{{{HT_NS}}}{tag}"


def _traffic_bonus(s: Optional[str]) -> float:
    """Returns additive bonus based on approximate traffic volume string."""
    if not s:
        return 0.0
    key = s.strip().rstrip("+").upper()
    return float(_TRAFFIC_BONUS.get(key, 0.0))


async def _fetch_feed(url: str, window: str) -> dict:
    """Returns {title_lower: {title, traffic, rank, articles}} from a feed."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch %s feed: %s", window, e)
        return {}

    results = {}
    try:
        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        if not channel:
            return {}

        for rank, item in enumerate(channel.findall("item"), start=1):
            title = (item.findtext("title") or "").strip()
            traffic = (item.findtext(_ht("approx_traffic")) or "").strip()
            if not title:
                continue

            embedded_articles = []
            for news_item in item.findall(_ht("news_item")):
                headline = (news_item.findtext(_ht("news_item_title")) or "").strip()
                url_link = (news_item.findtext(_ht("news_item_url")) or "").strip()
                source   = (news_item.findtext(_ht("news_item_source")) or "").strip()
                snippet  = (news_item.findtext(_ht("news_item_snippet")) or "").strip()
                if headline and url_link:
                    embedded_articles.append({"headline": headline, "url": url_link,
                                               "source": source, "snippet": snippet})

            results[title.lower()] = {
                "title": title,
                "traffic": traffic,
                "rank": rank,
                "articles": embedded_articles,
            }
    except ET.ParseError as e:
        logger.error("XML parse error for %s feed: %s", window, e)

    logger.info("Google Trends %s: %d topics", window, len(results))
    return results


async def fetch_google_trends_multi(db: Session) -> list:
    """Fetch 4h + 24h feeds, merge, score, upsert into Trend table."""
    now = datetime.now(timezone.utc)

    feed_24h, feed_4h = await _fetch_feed(RSS_24H, "24h"), await _fetch_feed(RSS_4H, "4h")

    all_titles = set(feed_24h.keys()) | set(feed_4h.keys())

    # Deactivate all current active trends — Google is the only source of situations
    db.query(Trend).filter(
        Trend.is_active == True,  # noqa: E712
    ).update({"is_active": False})

    trends = []
    for title_lower in all_titles:
        in_24h = title_lower in feed_24h
        in_4h  = title_lower in feed_4h
        entry  = feed_24h.get(title_lower) or feed_4h.get(title_lower)

        title   = entry["title"]
        traffic = entry["traffic"]
        rank    = entry["rank"]
        embedded_articles = entry["articles"]

        if in_24h and in_4h:
            window = "both"
            base_signal = SIGNAL_BOTH
        elif in_4h:
            window = "4h"
            base_signal = SIGNAL_4H_ONLY
        else:
            window = "24h"
            base_signal = SIGNAL_24H_ONLY

        signal = base_signal + _traffic_bonus(traffic)

        source_tags = []
        if in_4h:
            source_tags.append("google_4h")
        if in_24h:
            source_tags.append("google_24h")

        existing = (
            db.query(Trend)
            .filter(Trend.title.ilike(title))
            .first()
        )

        if existing:
            existing.is_active = True
            existing.fetched_at = now
            existing.traffic_volume = traffic
            existing.signal_score = signal
            existing.sources_list = list(set((existing.sources_list or []) + source_tags))
            existing.trend_window = window
            existing.appearance_count = (existing.appearance_count or 0) + 1
            trend = existing
        else:
            trend = Trend(
                title=title,
                source="rss",
                is_active=True,
                first_seen_at=now,
                appearance_count=1,
                signal_score=signal,
                sources_list=source_tags,
                trend_window=window,
                traffic_volume=traffic,
                geo="US",
            )
            db.add(trend)
            db.flush()

        # Upsert snapshot
        db.add(TrendSnapshot(trend_id=trend.id, traffic_volume=traffic, rank=rank, captured_at=now))

        # Upsert embedded articles
        db.query(Article).filter(Article.trend_id == trend.id).delete()
        for a in embedded_articles[:5]:
            db.add(Article(
                trend_id=trend.id,
                headline=a["headline"][:500],
                url=a["url"],
                source=a["source"],
                description=a["snippet"] or None,
            ))

        trends.append(trend)

    db.commit()
    logger.info(
        "Google Trends multi: %d total (%d 4h-only, %d 24h-only, %d both)",
        len(trends),
        sum(1 for t in trends if t.trend_window == "4h"),
        sum(1 for t in trends if t.trend_window == "24h"),
        sum(1 for t in trends if t.trend_window == "both"),
    )
    return trends
