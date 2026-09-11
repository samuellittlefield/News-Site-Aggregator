import logging
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend, WikiPage

logger = logging.getLogger(__name__)

SEARCH_URL = "https://en.wikipedia.org/w/api.php"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}
MAX_WIKI_PAGES = 3


def _title_overlaps(trend_title: str, wiki_title: str) -> bool:
    trend_words = set(trend_title.lower().split())
    wiki_words = set(wiki_title.lower().split())
    if not trend_words:
        return False
    return len(trend_words & wiki_words) / len(trend_words) >= 0.4


async def _fetch_summary(client: httpx.AsyncClient, wiki_title: str) -> Optional[dict]:
    encoded = urllib.parse.quote(wiki_title.replace(" ", "_"))
    resp = await client.get(SUMMARY_URL.format(encoded))
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("type") == "disambiguation":
        return None
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    extract = (data.get("extract") or "").strip()
    if not url or not extract:
        return None
    return {
        "title": data.get("title", wiki_title),
        "description": (data.get("description") or "").strip() or None,
        "extract": extract,
        "url": url,
        "thumbnail_url": (data.get("thumbnail") or {}).get("source"),
    }


async def fetch_wiki(trend: Trend, db: Session) -> List[WikiPage]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
        search_resp = await client.get(
            SEARCH_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": trend.title,
                "utf8": "",
                "format": "json",
                "srlimit": MAX_WIKI_PAGES,
            },
        )
        if search_resp.status_code != 200:
            logger.warning("Wikipedia search failed for '%s'", trend.title)
            return []

        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return []

        # Fetch summaries for each result that passes the overlap check
        candidates = []
        for result in results:
            wiki_title = result["title"]
            if not _title_overlaps(trend.title, wiki_title):
                continue
            summary = await _fetch_summary(client, wiki_title)
            if summary:
                candidates.append(summary)

    if not candidates:
        logger.info("No usable Wikipedia results for '%s'", trend.title)
        return []

    # Remove existing wiki pages for this trend and replace with fresh set
    for existing in trend.wiki_pages:
        db.delete(existing)
    db.flush()

    now = datetime.now(timezone.utc)
    pages = []
    for rank, candidate in enumerate(candidates[:MAX_WIKI_PAGES], start=1):
        page = WikiPage(
            trend_id=trend.id,
            is_primary=(rank == 1),
            search_rank=rank,
            title=candidate["title"],
            description=candidate["description"],
            extract=candidate["extract"],
            url=candidate["url"],
            thumbnail_url=candidate["thumbnail_url"],
            fetched_at=now,
        )
        db.add(page)
        pages.append(page)

    db.commit()
    logger.info(
        "Saved %d Wikipedia page(s) for '%s': %s",
        len(pages), trend.title,
        ", ".join(p.title for p in pages),
    )
    return pages
