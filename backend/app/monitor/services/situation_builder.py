"""
Situation Builder.

After all enrichment sources have run, generates cross-source AI summaries
for active trends that have been validated by multiple sources.

For trends validated by 2+ sources (e.g. Google + NYT, or Google + Wikipedia),
replaces the existing Groq summary with a richer synthesis that explains
*why* this is trending across multiple independent signals.
"""
import json
import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Summary, Trend

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SOURCE_LABELS = {
    "google_4h":  "breaking Google Trends (last 4 hours)",
    "google_24h": "Google Trends (today)",
    "nyt_shared": "New York Times (most shared)",
    "nyt_emailed":"New York Times (most emailed)",
    "nyt_home":   "New York Times homepage",
    "nyt_us":     "New York Times US section",
    "nyt_world":  "New York Times World section",
    "wikipedia":  "Wikipedia (pageview spike today)",
}


def _describe_sources(sources_list: list) -> str:
    labels = [SOURCE_LABELS.get(s, s) for s in sources_list if s]
    if not labels:
        return "Google Trends"
    return ", ".join(labels)


async def build_situation_summaries(db: Session) -> int:
    """
    Generate cross-source summaries for trending situations with 2+ validating sources.
    Returns count of summaries updated.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — skipping situation synthesis")
        return 0

    # Only process trends validated by 2+ independent source types
    active = (
        db.query(Trend)
        .filter(
            Trend.is_active == True,  # noqa
            Trend.source == "rss",
        )
        .order_by(Trend.signal_score.desc())
        .all()
    )

    multi_source = [
        t for t in active
        if len(t.sources_list or []) >= 2
    ]

    if not multi_source:
        logger.info("Situation builder: no multi-source trends found")
        return 0

    now = datetime.now(timezone.utc)
    updated = 0

    for trend in multi_source[:20]:  # cap to avoid excessive API calls
        try:
            # Gather supporting evidence
            articles = (
                db.query(Article)
                .filter(Article.trend_id == trend.id)
                .limit(5)
                .all()
            )
            article_lines = [
                f"- {a.headline}: {a.description or ''}"
                for a in articles if a.headline
            ]

            sources_desc = _describe_sources(trend.sources_list)
            traffic_desc = f" ({trend.traffic_volume} searches)" if trend.traffic_volume else ""

            prompt = (
                f'Topic: "{trend.title}"{traffic_desc}\n'
                f"Validated by: {sources_desc}\n"
            )
            if article_lines:
                prompt += f"\nRelated headlines:\n" + "\n".join(article_lines[:4])

            prompt += (
                f'\n\nWrite a 2-sentence situation briefing explaining why "{trend.title}" '
                f"is trending and what makes it significant right now. "
                f"Be specific, factual, and reference the cross-source validation where relevant."
            )

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GROQ_API_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 180,
                        "temperature": 0.3,
                    },
                )

            if resp.status_code != 200:
                continue

            body = resp.json()["choices"][0]["message"]["content"].strip()

            # Upsert the summary
            existing = db.query(Summary).filter(Summary.trend_id == trend.id).first()
            if existing:
                existing.body = body
                existing.generated_at = now
            else:
                db.add(Summary(trend_id=trend.id, body=body, generated_at=now))

            updated += 1

        except Exception as e:
            logger.warning("Situation synthesis failed for '%s': %s", trend.title, e)

    db.commit()
    logger.info("Situation builder: synthesized %d/%d multi-source summaries", updated, len(multi_source))
    return updated
