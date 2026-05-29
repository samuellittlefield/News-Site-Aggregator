"""
Wikipedia Trending Service.
Fetches the most-viewed English Wikipedia articles for today and yesterday,
finds articles that spiked significantly (new entries or large rank jumps),
and creates Trend records for ones that don't already exist.
"""
import logging
import os
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend

logger = logging.getLogger(__name__)

PAGEVIEW_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{year}/{month:02d}/{day:02d}"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}

# Articles that are always popular but not "trending" in a meaningful way
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
    """
    Score a Wikipedia article:
    - Not in yesterday's top 50 but in today's top 50 → spike bonus
    - Rank improved significantly → moderate bonus
    - Fallback: use raw view count
    """
    base = min(views / 1000, 150.0)  # cap at 150 for view count alone

    if rank_yesterday is None:
        # Brand-new entry in top 50 — significant signal
        return base + 200.0
    rank_delta = rank_yesterday - rank_today  # positive = moved up
    if rank_delta >= 20:
        return base + 150.0
    if rank_delta >= 10:
        return base + 80.0
    if rank_delta >= 5:
        return base + 40.0
    return base


async def fetch_wikipedia_trending(db: Session) -> list:
    today = date.today()
    yesterday = today - timedelta(days=1)

    def _url(d: date) -> str:
        return PAGEVIEW_URL.format(year=d.year, month=d.month, day=d.day)

    def _articles(resp) -> list:
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [{}])
        return items[0].get("articles", [])[:100] if items else []

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            # Try today first; if 404 (UTC date ahead of data availability), fall back
            r_today = await client.get(_url(today))
            if r_today.status_code == 404:
                r_today = await client.get(_url(yesterday))
                yesterday = yesterday - timedelta(days=1)  # shift baseline back one more day
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
            return []

        logger.info("Wikipedia: loaded %d articles for trending analysis", len(articles_today))
    except Exception as e:
        logger.error("Wikipedia trending fetch failed: %s", e)
        return []

    # Build title → active trend lookup (case-insensitive)
    active_titles = {t.title.lower(): t for t in db.query(Trend).filter(Trend.is_active == True).all()}  # noqa

    now = datetime.now(timezone.utc)
    groq_key = os.getenv("GROQ_API_KEY")
    new_trends = []

    for article_title, today_data in articles_today.items():
        if _is_perennial(article_title):
            continue

        title_clean = article_title.replace("_", " ")
        ydata = articles_yesterday.get(article_title)
        wiki_sig = _wiki_signal(today_data["rank"], ydata["rank"] if ydata else None, today_data["views"])

        # Check for exact or near-match with existing active trends — boost rather than duplicate
        title_words = set(title_clean.lower().split())
        matched_existing = None
        if title_clean.lower() in active_titles:
            matched_existing = active_titles[title_clean.lower()]
        else:
            for active_title, active_trend in active_titles.items():
                overlap = len(title_words & set(active_title.split())) / max(len(title_words), 1)
                if overlap >= 0.6:
                    matched_existing = active_trend
                    break

        if matched_existing:
            # Absorb Wikipedia signal into the existing entry (RSS or other source)
            matched_existing.signal_score = matched_existing.signal_score + wiki_sig * 0.5
            continue

        ydata = articles_yesterday.get(article_title)
        signal = _wiki_signal(today_data["rank"], ydata["rank"] if ydata else None, today_data["views"])

        # Only create trend if signal is meaningful
        if signal < 80:
            continue

        # Generate a Groq summary if available
        summary_text = None
        if groq_key:
            try:
                import httpx as _httpx
                sr = await _httpx.AsyncClient(timeout=12.0).post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content":
                            f'"{title_clean}" is trending on Wikipedia today. '
                            f'Write 1-2 sentences explaining what this is and why people might be looking it up. Be concise.'}],
                        "max_tokens": 120,
                        "temperature": 0.3,
                        "response_format": {"type": "text"},
                    },
                )
                if sr.status_code == 200:
                    summary_text = sr.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        trend = Trend(
            title=title_clean,
            source="wikipedia",
            is_active=True,
            first_seen_at=now,
            appearance_count=1,
            signal_score=signal,
            geo="Global",
            traffic_volume=f"{today_data['views']:,}",
        )
        db.add(trend)
        db.flush()

        if summary_text:
            from app.models import Summary
            db.add(Summary(trend_id=trend.id, body=summary_text, generated_at=now))

        new_trends.append(trend)

        if len(new_trends) >= 15:
            break

    db.commit()
    logger.info("Wikipedia trending: %d new trends added", len(new_trends))
    return new_trends
