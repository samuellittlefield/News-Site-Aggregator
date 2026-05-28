import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Summary, Trend

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


async def generate_summary(trend: Trend, articles: list, db: Session) -> Optional[Summary]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — skipping summary generation")
        return None

    article_lines = [
        f"- {a.headline}: {a.description or ''}"
        for a in articles
        if a.headline
    ]
    if not article_lines:
        return None

    CATEGORIES = "Sports, Politics, Entertainment, Technology, Business, Crime, Science, Culture, Other"

    prompt = (
        f'Trending topic: "{trend.title}"\n\n'
        f"Related news:\n" + "\n".join(article_lines) + "\n\n"
        f"Respond with a JSON object containing exactly two fields:\n"
        f'- "summary": a 2-3 sentence briefing explaining why "{trend.title}" is trending and what is happening. Be concise and factual.\n'
        f'- "category": classify the topic as exactly one of: {CATEGORIES}\n\n'
        f"Return only the JSON object, no other text."
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
        if resp.status_code != 200:
            logger.warning("Groq returned %s for '%s'", resp.status_code, trend.title)
            return None
    except httpx.RequestError as e:
        logger.error("Groq request failed: %s", e)
        return None

    raw = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        parsed = json.loads(raw)
        body = parsed.get("summary", raw).strip()
        category = parsed.get("category", "Other").strip()
    except (json.JSONDecodeError, KeyError):
        body = raw
        category = "Other"

    # Persist the category back onto the trend
    if not trend.category:
        trend.category = category
        db.add(trend)

    now = datetime.now(timezone.utc)

    existing = db.query(Summary).filter(Summary.trend_id == trend.id).first()
    if existing:
        existing.body = body
        existing.generated_at = now
        db.commit()
        return existing

    summary = Summary(trend_id=trend.id, body=body, generated_at=now)
    db.add(summary)
    db.commit()
    return summary
