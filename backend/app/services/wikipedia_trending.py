"""
Wikipedia Trending enrichment service.

Two roles:
1. BOOST existing active Trends when a Wikipedia article is spiking on the same topic.
2. CREATE standalone Trend entries for large Wikipedia spikes (rank jumped 20+ positions)
   with no Google Trends match — surfacing genuinely viral topics early.

Returns the count of existing trends boosted.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend
from app.services.topic_matcher import find_match

logger = logging.getLogger(__name__)

PAGEVIEW_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{year}/{month:02d}/{day:02d}"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}
MAX_STANDALONE = 5

PERENNIAL_BLOCKLIST = {
    "main page", "special:search", "wikipedia", "united states", "india",
    "china", "united kingdom", "canada", "australia", "france", "germany",
    "russia", "brazil", "mexico", "italy", "spain", "japan", "south korea",
    "youtube", "google", "facebook", "instagram", "twitter",
    "deaths in 2024", "deaths in 2025", "deaths in 2026",
    "portal:", "help:", "wikipedia:", "talk:", "user:",
    "list of", "outline of",
}


def _is_perennial(title: str) -> bool:
    t = title.lower()
    return any(p in t for p in PERENNIAL_BLOCKLIST)


def _wiki_signal(rank_today: int, rank_yesterday: Optional[int], views: int) -> float:
    base = min(views / 1000, 150.0)
    if rank_yesterday is None:
        return base + 200.0
    rank_delta = rank_yesterday - rank_today
    if rank_delta >= 20:
        return base + 150.0
    if rank_delta >= 10:
        return base + 80.0
    if rank_delta >= 5:
        return base + 40.0
    return base


def _url(d: date) -> str:
    return PAGEVIEW_URL.format(year=d.year, month=d.month, day=d.day)


def _articles(resp) -> list:
    if resp.status_code != 200:
        return []
    items = resp.json().get("items", [{}])
    return items[0].get("articles", [])[:100] if items else []


async def fetch_wikipedia_trending(db: Session) -> int:
    active_trends = (
        db.query(Trend)
        .filter(Trend.is_active == True)  # noqa
        .all()
    )

    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            r_today = await client.get(_url(today))
            if r_today.status_code == 404:
                r_today = await client.get(_url(yesterday))
                yesterday = yesterday - timedelta(days=1)
            r_yesterday = await client.get(_url(yesterday))

        articles_today = {
            a["article"]: {"rank": a["rank"], "views": a["views"]}
            for a in _articles(r_today)
        }
        articles_yesterday = {
            a["article"]: {"rank": a["rank"]}
            for a in _articles(r_yesterday)
        }

        if not articles_today:
            logger.warning("Wikipedia: no articles available for any recent date")
            return 0

        logger.info("Wikipedia: loaded %d articles for enrichment", len(articles_today))
    except Exception as e:
        logger.error("Wikipedia trending fetch failed: %s", e)
        return 0

    boosted_ids: set = set()
    standalone_created = 0
    now = datetime.now(timezone.utc)

    for article_title, today_data in articles_today.items():
        if _is_perennial(article_title):
            continue

        title_clean = article_title.replace("_", " ")
        ydata = articles_yesterday.get(article_title)
        wiki_sig = _wiki_signal(today_data["rank"], ydata["rank"] if ydata else None, today_data["views"])

        if wiki_sig < 80:
            continue

        match = find_match(title_clean, active_trends, threshold=0.50)

        if match:
            boost = wiki_sig * 0.5
            match.signal_score += boost
            match.sources_list = list(set((match.sources_list or []) + ["wikipedia"]))
            boosted_ids.add(match.id)
            logger.debug("Wikipedia boost: '%s' → '%s' +%.0f", title_clean[:40], match.title[:40], boost)
        elif standalone_created < MAX_STANDALONE:
            # Large spike with no Google match — check if it warrants standalone entry
            rank_delta = (ydata["rank"] - today_data["rank"]) if ydata else 999
            if rank_delta >= 20 or ydata is None:
                base_signal = wiki_sig * 0.7
                trend = Trend(
                    title=title_clean,
                    source="wikipedia",
                    is_active=True,
                    first_seen_at=now,
                    fetched_at=now,
                    appearance_count=1,
                    signal_score=base_signal,
                    sources_list=["wikipedia"],
                    geo="US",
                    traffic_volume=f"{today_data['views'] // 1000}K views",
                )
                db.add(trend)
                active_trends.append(trend)
                standalone_created += 1
                logger.info("Wikipedia standalone: '%s' (%.0f signal, rank delta %+d)", title_clean[:60], base_signal, rank_delta)

    db.commit()
    logger.info("Wikipedia enrichment: boosted %d existing trends, created %d standalone", len(boosted_ids), standalone_created)
    return len(boosted_ids)
