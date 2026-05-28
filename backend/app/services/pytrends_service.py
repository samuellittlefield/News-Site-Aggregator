import asyncio
import logging
from datetime import datetime, timezone
from functools import partial

from sqlalchemy.orm import Session

from app.models import Article, Trend
from app.services.news import fetch_articles
from app.services.summarizer import generate_summary
from app.services.wikipedia import fetch_wiki
from app.services.velocity import compute_velocity

logger = logging.getLogger(__name__)


def _sync_fetch_breakout(active_titles: set) -> list:
    """
    Runs synchronously in a thread — pytrends is not async.
    Uses realtime_trending_searches which returns story-level trending topics.
    Returns topic titles not already in the active RSS feed.
    """
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        df = pt.realtime_trending_searches(pn="US")
        # df columns vary by pytrends version; title is typically in 'title' or first col
        title_col = "title" if "title" in df.columns else df.columns[0]
        topics = df[title_col].dropna().tolist()
        return [t for t in topics if t.lower() not in active_titles]
    except Exception as e:
        logger.warning("pytrends fetch failed (non-fatal): %s", e)
        return []


async def fetch_breakout_trends(db: Session) -> list:
    """
    Find topics trending on Google that are NOT in our RSS top feed.
    Creates Trend records for new topics and enriches them with
    articles, summaries, and Wikipedia data.
    """
    active_titles = {
        t.title.lower()
        for t in db.query(Trend).filter(Trend.is_active == True).all()  # noqa: E712
    }

    loop = asyncio.get_event_loop()
    new_titles = await loop.run_in_executor(None, partial(_sync_fetch_breakout, active_titles))

    if not new_titles:
        logger.info("pytrends: no breakout topics outside current RSS feed")
        return []

    now = datetime.now(timezone.utc)
    trends = []
    for title in new_titles[:10]:
        existing = db.query(Trend).filter(Trend.title == title).first()
        if existing:
            existing.is_active = True
            existing.fetched_at = now
            existing.appearance_count = (existing.appearance_count or 0) + 1
            trend = existing
        else:
            trend = Trend(
                title=title,
                source="pytrends",
                is_active=True,
                first_seen_at=now,
                appearance_count=1,
            )
            db.add(trend)
            db.flush()
        trends.append(trend)

    db.commit()
    logger.info("pytrends: %d breakout topics found", len(trends))

    # Enrich each breakout trend
    for trend in trends:
        articles = await fetch_articles(trend, db)
        await generate_summary(trend, articles, db)
        await fetch_wiki(trend, db)
        compute_velocity(trend, db)

    db.commit()
    return trends
