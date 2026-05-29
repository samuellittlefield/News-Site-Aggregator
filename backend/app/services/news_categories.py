import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import NewsArticle

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0"}

FEEDS = {
    "politics": (
        "https://news.google.com/rss/search"
        "?q=US+politics+congress+senate+president+election&hl=en-US&gl=US&ceid=US:en"
    ),
    "transportation": (
        "https://news.google.com/rss/search"
        "?q=electric+vehicles+OR+public+transit+OR+Amtrak+OR+aviation+OR+Tesla&hl=en-US&gl=US&ceid=US:en"
    ),
}


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        return None


async def _summarize(title: str, description: str, api_key: str) -> Optional[str]:
    prompt = (
        f'News headline: "{title}"\n'
        f"Brief context: {(description or '')[:200]}\n\n"
        f"Write one sentence summarizing the key development. Be factual and concise."
    )
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 80,
                    "temperature": 0.2,
                },
            )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


async def fetch_news_category(category: str, db: Session) -> list:
    feed_url = FEEDS.get(category)
    if not feed_url:
        return []

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            resp = await client.get(feed_url)
        resp.raise_for_status()
    except httpx.RequestError as e:
        logger.error("News feed fetch failed for %s: %s", category, e)
        return []

    try:
        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        items = channel.findall("item") if channel else []
    except ET.ParseError as e:
        logger.error("News feed parse error for %s: %s", category, e)
        return []

    api_key = os.getenv("GROQ_API_KEY")
    now = datetime.now(timezone.utc)

    # Clear old articles for this category
    db.query(NewsArticle).filter(NewsArticle.category == category).delete()

    articles = []
    for item in items[:12]:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        source_el = item.find("source")
        source = source_el.text if source_el is not None else ""
        pub_str = item.findtext("pubDate")
        description = (item.findtext("description") or "").strip()
        # Strip HTML tags from description
        import re
        description = re.sub(r"<[^>]+>", "", description).strip()

        if not title or not url:
            continue

        pub_date = _parse_date(pub_str)
        summary = await _summarize(title, description, api_key) if api_key else None

        article = NewsArticle(
            category=category,
            title=title,
            url=url,
            source=source,
            published_at=pub_date,
            description=description[:500] if description else None,
            ai_summary=summary,
            fetched_at=now,
        )
        db.add(article)
        articles.append(article)

    db.commit()
    logger.info("News category '%s': stored %d articles", category, len(articles))
    return articles
