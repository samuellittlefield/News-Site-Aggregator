import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Trend

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"


async def fetch_articles(trend: Trend, db: Session) -> list:
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("NEWSAPI_KEY not set — skipping article fetch")
        return []

    # Remove stale articles before refreshing
    db.query(Article).filter(Article.trend_id == trend.id).delete()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NEWSAPI_URL,
                params={
                    "q": trend.title,
                    "pageSize": 5,
                    "sortBy": "relevancy",
                    "language": "en",
                    "apiKey": api_key,
                },
            )
        if resp.status_code != 200:
            logger.warning("NewsAPI returned %s for '%s'", resp.status_code, trend.title)
            db.commit()
            return []
    except httpx.RequestError as e:
        logger.error("NewsAPI request failed: %s", e)
        db.commit()
        return []

    articles = []
    for item in resp.json().get("articles", []):
        published = None
        if pub := item.get("publishedAt"):
            try:
                published = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except ValueError:
                pass

        article = Article(
            trend_id=trend.id,
            headline=(item.get("title") or "")[:500],
            url=item.get("url") or "",
            source=(item.get("source") or {}).get("name") or "",
            published_at=published,
            description=item.get("description") or "",
        )
        db.add(article)
        articles.append(article)

    db.commit()
    logger.info("Stored %d articles for '%s'", len(articles), trend.title)
    return articles
