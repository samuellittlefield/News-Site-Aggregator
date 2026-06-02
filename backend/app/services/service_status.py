"""
Service Health Monitor.
Polls public Statuspage.io APIs from major internet services.
All services below publish free, unauthenticated status JSON.
"""
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import ServiceStatus

logger = logging.getLogger(__name__)

SERVICES = [
    {"name": "GitHub",       "url": "https://www.githubstatus.com/api/v2/status.json",       "icon": "🐙", "page": "https://www.githubstatus.com"},
    {"name": "Cloudflare",   "url": "https://www.cloudflarestatus.com/api/v2/status.json",   "icon": "🌐", "page": "https://www.cloudflarestatus.com"},
    {"name": "OpenAI",       "url": "https://status.openai.com/api/v2/status.json",           "icon": "🤖", "page": "https://status.openai.com"},
    {"name": "Reddit",       "url": "https://www.redditstatus.com/api/v2/status.json",        "icon": "🔴", "page": "https://www.redditstatus.com"},
    {"name": "Vercel",       "url": "https://www.vercel-status.com/api/v2/status.json",       "icon": "▲",  "page": "https://www.vercel-status.com"},
    {"name": "Stripe",       "url": "https://status.stripe.com/api/v2/status.json",           "icon": "💳", "page": "https://status.stripe.com"},
    {"name": "Shopify",      "url": "https://www.shopifystatus.com/api/v2/status.json",       "icon": "🛍️", "page": "https://www.shopifystatus.com"},
    {"name": "Atlassian",    "url": "https://status.atlassian.com/api/v2/status.json",        "icon": "🔷", "page": "https://status.atlassian.com"},
    {"name": "Twilio",       "url": "https://status.twilio.com/api/v2/status.json",           "icon": "📱", "page": "https://status.twilio.com"},
    {"name": "Discord",      "url": "https://discordstatus.com/api/v2/status.json",           "icon": "💬", "page": "https://discordstatus.com"},
    {"name": "Notion",       "url": "https://status.notion.so/api/v2/status.json",            "icon": "📝", "page": "https://status.notion.so"},
    {"name": "Linear",       "url": "https://linearstatus.com/api/v2/status.json",            "icon": "📐", "page": "https://linearstatus.com"},
    {"name": "Anthropic",    "url": "https://status.claude.com/api/v2/status.json",           "icon": "🧠", "page": "https://status.claude.com"},
]

INDICATOR_ORDER = {"critical": 0, "major": 1, "minor": 2, "none": 3}


async def fetch_service_statuses(db: Session) -> list:
    now = datetime.now(timezone.utc)
    results = []

    async with httpx.AsyncClient(timeout=8.0) as client:
        for svc in SERVICES:
            try:
                resp = await client.get(svc["url"])
                if resp.status_code != 200:
                    continue
                data = resp.json()
                status = data.get("status", {})
                indicator = status.get("indicator", "none")
                description = status.get("description", "")

                existing = db.query(ServiceStatus).filter(ServiceStatus.name == svc["name"]).first()
                if existing:
                    existing.indicator = indicator
                    existing.description = description
                    existing.fetched_at = now
                    results.append(existing)
                else:
                    row = ServiceStatus(
                        name=svc["name"],
                        indicator=indicator,
                        description=description,
                        icon=svc["icon"],
                        page_url=svc["page"],
                        fetched_at=now,
                    )
                    db.add(row)
                    results.append(row)

            except Exception as e:
                logger.debug("Status fetch failed for %s: %s", svc["name"], e)

    db.commit()

    # Sort: incidents first, then alphabetical
    results.sort(key=lambda r: (INDICATOR_ORDER.get(r.indicator, 99), r.name))
    logger.info("Service status: polled %d/%d services", len(results), len(SERVICES))
    return results
