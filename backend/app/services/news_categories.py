import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import NewsArticle
from app.services.gdelt import query_gdelt

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0"}

FEEDS = {
    "politics": (
        "https://news.google.com/rss/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNRFZ4WVZZAE"
        "?hl=en-US&gl=US&ceid=US:en"
    ),
    "politics_fallback": (
        "https://news.google.com/rss/search"
        "?q=US+congress+senate+white+house+president+election+legislation&hl=en-US&gl=US&ceid=US:en"
    ),
    "transportation": (
        "https://news.google.com/rss/search"
        "?q=electric+vehicles+OR+EV+OR+public+transit+OR+Amtrak+OR+aviation+OR+Tesla+OR+autonomous+vehicles&hl=en-US&gl=US&ceid=US:en"
    ),
}

# GDELT queries per category — fresher than Google News RSS (15-min index)
GDELT_QUERIES = {
    "politics": '(congress OR senate OR "white house" OR election OR governor)',
    "transportation": '(FAA OR Amtrak OR "ground stop" OR "public transit" OR aviation OR "electric vehicle")',
}

MAX_CATEGORY_ARTICLES = 12


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


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


async def _fetch_rss_items(category: str) -> list:
    """Google News RSS items for a category; empty list on any failure —
    RSS is supplementary to GDELT and must never abort the refresh."""
    feed_url = FEEDS.get(category)
    if not feed_url:
        return []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            resp = await client.get(feed_url)
            # Fallback for politics if topic ID returns empty or errors
            if category == "politics":
                items_ok = False
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    channel = root.find("channel")
                    items_ok = channel is not None and len(channel.findall("item")) >= 3
                if not items_ok:
                    fallback_url = FEEDS.get("politics_fallback")
                    if fallback_url:
                        resp = await client.get(fallback_url)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        return channel.findall("item") if channel else []
    except (httpx.RequestError, httpx.HTTPStatusError, ET.ParseError) as e:
        logger.warning("News feed fetch failed for %s: %s", category, e)
        return []


async def fetch_news_category(category: str, db: Session) -> list:
    items = await _fetch_rss_items(category)

    # Collect candidates from both sources: GDELT first (fresher), then RSS
    candidates: list[dict] = []

    gdelt_query = GDELT_QUERIES.get(category)
    if gdelt_query:
        for art in await query_gdelt(gdelt_query, timespan="24h", maxrecords=MAX_CATEGORY_ARTICLES):
            candidates.append({
                "title": art["title"],
                "url": art["url"],
                "source": art["domain"],
                "published_at": art.get("published_at"),
                "description": "",
            })

    for item in items:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        source_el = item.find("source")
        description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()
        candidates.append({
            "title": title,
            "url": url,
            "source": source_el.text if source_el is not None else "",
            "published_at": _parse_date(item.findtext("pubDate")),
            "description": description,
        })

    # Dedupe by normalized URL and title
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for c in candidates:
        url_key = c["url"].split("?")[0].rstrip("/")
        title_key = _normalize_title(c["title"])
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        deduped.append(c)
        if len(deduped) >= MAX_CATEGORY_ARTICLES:
            break

    if not deduped:
        logger.warning("News category '%s': no articles from any source", category)
        return []

    api_key = os.getenv("GROQ_API_KEY")
    now = datetime.now(timezone.utc)

    # Clear old articles for this category
    db.query(NewsArticle).filter(NewsArticle.category == category).delete()

    articles = []
    for c in deduped:
        summary = await _summarize(c["title"], c["description"], api_key) if api_key else None
        article = NewsArticle(
            category=category,
            title=c["title"],
            url=c["url"],
            source=c["source"],
            published_at=c["published_at"],
            description=c["description"][:500] if c["description"] else None,
            ai_summary=summary,
            fetched_at=now,
        )
        db.add(article)
        articles.append(article)

    db.commit()
    logger.info("News category '%s': stored %d articles", category, len(articles))
    return articles
