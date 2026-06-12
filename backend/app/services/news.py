import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Trend
from app.services.gdelt import query_gdelt

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
MAX_ARTICLES = 5


async def _fetch_newsapi(trend: Trend) -> list[dict]:
    """Fallback source — free tier delays articles 24h."""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NEWSAPI_URL,
                params={
                    "q": trend.title,
                    "pageSize": MAX_ARTICLES,
                    "sortBy": "relevancy",
                    "language": "en",
                    "apiKey": api_key,
                },
            )
        if resp.status_code != 200:
            logger.warning("NewsAPI returned %s for '%s'", resp.status_code, trend.title)
            return []
    except httpx.RequestError as e:
        logger.error("NewsAPI request failed: %s", e)
        return []

    items = []
    for item in resp.json().get("articles", []):
        published = None
        if pub := item.get("publishedAt"):
            try:
                published = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except ValueError:
                pass
        items.append({
            "title": item.get("title") or "",
            "url": item.get("url") or "",
            "domain": (item.get("source") or {}).get("name") or "",
            "published_at": published,
            "description": item.get("description") or "",
        })
    return items


async def fetch_articles(trend: Trend, db: Session) -> list:
    """GDELT-first (realtime, 15-min index); NewsAPI fallback when GDELT is thin."""
    items = await query_gdelt(f'"{trend.title}"', timespan="48h", maxrecords=MAX_ARTICLES)
    if len(items) < 2:
        items = await _fetch_newsapi(trend) or items

    if not items:
        # Both sources came up empty — keep whatever we already have
        return []

    # Remove stale articles before refreshing
    db.query(Article).filter(Article.trend_id == trend.id).delete()

    articles = []
    for item in items[:MAX_ARTICLES]:
        article = Article(
            trend_id=trend.id,
            headline=item["title"][:500],
            url=item["url"],
            source=item["domain"],
            published_at=item.get("published_at"),
            description=item.get("description") or "",
        )
        db.add(article)
        articles.append(article)

    db.commit()
    logger.info("Stored %d articles for '%s'", len(articles), trend.title)
    return articles
