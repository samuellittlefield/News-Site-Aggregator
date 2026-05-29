"""
New York Times RSS service.
Fetches the NYT homepage, Most Shared, and Most Emailed feeds.
Creates Trend entries for top stories and boosts existing trends
that have matching NYT coverage.
"""
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Summary, Trend

logger = logging.getLogger(__name__)

NYT_FEEDS = [
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MostShared.xml",   "weight": 200, "tag": "nyt_shared"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MostEmailed.xml",  "weight": 180, "tag": "nyt_emailed"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",     "weight": 150, "tag": "nyt_home"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",           "weight": 130, "tag": "nyt_us"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",        "weight": 120, "tag": "nyt_world"},
]

HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_pub_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        return None


def _title_overlap(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


async def _maybe_summarize(title: str, description: str, api_key: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content":
                        f'NYT headline: "{title}"\n{description[:200]}\n\n'
                        f'Write one sentence summarizing the key development. Be factual and concise.'}],
                    "max_tokens": 80,
                    "temperature": 0.2,
                },
            )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


async def fetch_nyt_trending(db: Session) -> list:
    now = datetime.now(timezone.utc)
    api_key = os.getenv("GROQ_API_KEY")

    # Get all active trends for dedup / boost
    active_trends = db.query(Trend).filter(Trend.is_active == True).all()  # noqa
    active_map = {t.title.lower(): t for t in active_trends}

    seen_urls: set = set()
    new_trends = []

    for feed_info in NYT_FEEDS:
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
                resp = await client.get(feed_info["url"])
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            items = channel.findall("item") if channel else []
        except Exception as e:
            logger.warning("NYT feed %s failed: %s", feed_info["tag"], e)
            continue

        for item in items[:15]:
            title = (item.findtext("title") or "").strip()
            url   = (item.findtext("link")  or "").strip()
            desc  = _strip_html(item.findtext("description") or "")
            pub_s = item.findtext("pubDate")

            if not title or url in seen_urls:
                continue
            seen_urls.add(url)

            title_words = set(title.lower().split())

            # Check if this matches an existing active trend → boost signal
            boosted = False
            for active_title, active_trend in active_map.items():
                if _title_overlap(title, active_title) >= 0.45:
                    boost = feed_info["weight"] * 0.6
                    active_trend.signal_score = active_trend.signal_score + boost
                    src_list = list(set((active_trend.sources_list or []) + [feed_info["tag"]]))
                    active_trend.sources_list = src_list
                    boosted = True
                    logger.debug("NYT boost: '%s' → '%s' +%.0f", title[:40], active_title[:40], boost)
                    break

            if boosted:
                continue

            # New topic not in trending feed — create entry
            summary_text = await _maybe_summarize(title, desc, api_key) if api_key else None

            trend = Trend(
                title=title,
                source="nyt",
                is_active=True,
                first_seen_at=now,
                appearance_count=1,
                signal_score=float(feed_info["weight"]),
                sources_list=[feed_info["tag"]],
                trend_window="nyt",
                geo="US",
                traffic_volume=None,
            )
            db.add(trend)
            db.flush()

            if summary_text:
                db.add(Summary(trend_id=trend.id, body=summary_text, generated_at=now))

            new_trends.append(trend)
            active_map[title.lower()] = trend  # prevent duplicates from later feeds

            if len(new_trends) >= 12:
                break

        if len(new_trends) >= 12:
            break

    db.commit()
    logger.info("NYT: %d new trends added, boosts applied to existing", len(new_trends))
    return new_trends
