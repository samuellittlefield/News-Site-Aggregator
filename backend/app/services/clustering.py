import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Trend, TrendCluster

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


async def cluster_trends(db: Session) -> list:
    """
    Ask Groq to group active trends into named events/stories.
    Assigns cluster_id to each matched trend. Clears stale clusters first.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — skipping clustering")
        return []

    active = (
        db.query(Trend)
        .filter(Trend.is_active == True)  # noqa: E712
        .all()
    )
    if len(active) < 2:
        return []

    # Build topic list for the prompt
    topic_lines = []
    for t in active:
        summary_preview = ""
        if t.summary:
            summary_preview = t.summary.body[:100].replace("\n", " ")
        topic_lines.append(
            f'- "{t.title}" (category: {t.category or "Unknown"}): {summary_preview}'
        )

    prompt = (
        "You are grouping trending Google search topics into related news events.\n\n"
        "Topics:\n" + "\n".join(topic_lines) + "\n\n"
        "Identify groups of 2 or more topics that are clearly about the same event or story. "
        "Only cluster topics with strong thematic overlap. When in doubt, leave topics ungrouped.\n\n"
        "Return a JSON object with a 'clusters' array. Each cluster has:\n"
        '- "name": short event name (e.g. "French Open 2026")\n'
        '- "description": one sentence explaining the connection\n'
        '- "category": the dominant category (Sports, Politics, etc.)\n'
        '- "topics": list of exact topic titles from the input\n\n'
        "Return only the JSON, no other text."
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
        if resp.status_code != 200:
            logger.warning("Groq clustering failed: %s", resp.status_code)
            return []
    except httpx.RequestError as e:
        logger.error("Groq clustering request failed: %s", e)
        return []

    try:
        raw = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(raw)
        clusters_data = data.get("clusters", [])
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse clustering response: %s", e)
        return []

    # Clear existing clusters
    db.query(TrendCluster).delete()
    for t in active:
        t.cluster_id = None

    # Build a title → trend lookup
    title_map = {t.title.lower(): t for t in active}

    clusters = []
    now = datetime.now(timezone.utc)
    for c in clusters_data:
        topics = c.get("topics", [])
        matched = [title_map[topic.lower()] for topic in topics if topic.lower() in title_map]
        if len(matched) < 2:
            continue

        cluster = TrendCluster(
            name=c.get("name", "Related Topics"),
            description=c.get("description"),
            category=c.get("category"),
            generated_at=now,
        )
        db.add(cluster)
        db.flush()

        for trend in matched:
            trend.cluster_id = cluster.id

        clusters.append(cluster)
        logger.info("Cluster '%s': %s", cluster.name, [t.title for t in matched])

    db.commit()
    logger.info("Clustering complete — %d clusters from %d trends", len(clusters), len(active))
    return clusters
