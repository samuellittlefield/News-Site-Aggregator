import logging
import urllib.parse
from datetime import date, datetime, timedelta
from typing import List

import httpx
from sqlalchemy.orm import Session

from app.models import WikiPage, WikiPageView

logger = logging.getLogger(__name__)

PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia/all-access/all-agents/{title}/daily/{start}/{end}"
)
HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}
LOOKBACK_DAYS = 60


async def fetch_pageviews(wiki_page: WikiPage, db: Session) -> List[WikiPageView]:
    encoded = urllib.parse.quote(wiki_page.title.replace(" ", "_"), safe="")
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)

    url = PAGEVIEWS_URL.format(
        title=encoded,
        start=start.strftime("%Y%m%d00"),
        end=end.strftime("%Y%m%d00"),
    )

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
            resp = await client.get(url)
        if resp.status_code == 404:
            logger.info("No pageview data for '%s' (404)", wiki_page.title)
            return []
        resp.raise_for_status()
    except httpx.RequestError as e:
        logger.warning("Pageviews request failed for '%s': %s", wiki_page.title, e)
        return []

    items = resp.json().get("items", [])

    # Upsert: delete existing rows then re-insert (simpler than individual upserts)
    db.query(WikiPageView).filter(WikiPageView.wiki_page_id == wiki_page.id).delete()

    views = []
    for item in items:
        ts = item.get("timestamp", "")  # format: YYYYMMDD00
        try:
            view_date = datetime.strptime(ts[:8], "%Y%m%d").date()
        except (ValueError, TypeError):
            continue
        row = WikiPageView(
            wiki_page_id=wiki_page.id,
            view_date=view_date,
            views=item.get("views", 0),
        )
        db.add(row)
        views.append(row)

    db.commit()
    logger.info("Stored %d pageview records for '%s'", len(views), wiki_page.title)
    return views
