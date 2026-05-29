"""
Wikipedia Trending enrichment service.

Finds Wikipedia articles that are spiking in pageviews today vs. yesterday,
and BOOSTS the signal score of matching active Google Trends entries.
Never creates standalone Trend entries.

Returns the count of trends boosted.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend

logger = logging.getLogger(__name__)

PAGEVIEW_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{year}/{month:02d}/{day:02d}"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}

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


def _title_overlap(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def _url(d: date) -> str:
    return PAGEVIEW_URL.format(year=d.year, month=d.month, day=d.day)


def _articles(resp) -> list:
    if resp.status_code != 200:
        return []
    items = resp.json().get("items", [{}])
    return items[0].get("articles", [])[:100] if items else []


async def fetch_wikipedia_trending(db: Session) -> int:
    """
    Fetches Wikipedia pageview spikes and boosts matching active Google Trends.
    Returns count of trends boosted.
    """
    active_trends = (
        db.query(Trend)
        .filter(Trend.is_active == True, Trend.source == "rss")  # noqa
        .all()
    )
    if not active_trends:
        return 0

    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            r_today = await client.get(_url(today))
            # Fall back to yesterday if today's data isn't available yet (UTC server)
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

    active_map = {t.title.lower(): t for t in active_trends}
    boosted_ids: set = set()

    for article_title, today_data in articles_today.items():
        if _is_perennial(article_title):
            continue

        title_clean = article_title.replace("_", " ")
        ydata = articles_yesterday.get(article_title)
        wiki_sig = _wiki_signal(today_data["rank"], ydata["rank"] if ydata else None, today_data["views"])

        # Only process meaningful spikes
        if wiki_sig < 80:
            continue

        # Find best matching active Google Trend
        best_match: Optional[Trend] = None
        best_score = 0.0

        for active_title, trend in active_map.items():
            overlap = _title_overlap(title_clean, active_title)
            if overlap > best_score and overlap >= 0.50:
                best_score = overlap
                best_match = trend

        if best_match:
            boost = wiki_sig * 0.5
            best_match.signal_score = best_match.signal_score + boost
            src_list = list(set((best_match.sources_list or []) + ["wikipedia"]))
            best_match.sources_list = src_list
            boosted_ids.add(best_match.id)
            logger.debug(
                "Wikipedia boost: '%s' → '%s' +%.0f",
                title_clean[:40], best_match.title[:40], boost,
            )

    db.commit()
    logger.info("Wikipedia enrichment: boosted %d existing trends", len(boosted_ids))
    return len(boosted_ids)
